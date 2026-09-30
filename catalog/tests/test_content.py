import shutil
import tempfile
import textwrap
from io import StringIO
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from catalog.content import CONTENT_DIR, ContentError, load_content, sync_content
from catalog.models import Country, GeneralStep, Service, ServiceTranslation, StepTranslation
from initiators.models import Initiator, Project, ServiceApplication


class ContentFilesMixin:
    """Builds a small content directory in a temp folder."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        self.write('countries.yaml', """
            - code: AT
              name: Austria
              language: de
            - code: HR
              name: Croatia
              language: hr
        """)
        self.write('steps/planning/permits.yaml', """
            title: Permits
            sort_order: 10
            topic: PV Plant
            description: Get the permits.
        """)
        self.write('steps/realisation/construction.yaml', """
            title: Construction
            sort_order: 20
        """)
        self.write('services/at/building-permit.yaml', """
            name: 'AT: Building permit'
            step: permits
            summary: Apply for the building permit.
            description: |-
              Details about the permit.
              Second line.
            web_link: https://example.org/permit
        """)

    def write(self, rel, text):
        path = self.dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(text).lstrip(), encoding='utf-8')

    def remove(self, rel):
        (self.dir / rel).unlink()

    def sync(self, dry_run=False):
        return sync_content(load_content(self.dir), dry_run=dry_run)

    def assert_invalid(self, message):
        with self.assertRaises(ContentError) as ctx:
            load_content(self.dir)
        self.assertTrue(any(message in e for e in ctx.exception.errors), ctx.exception.errors)


class ValidationTests(ContentFilesMixin, TestCase):
    def test_valid_content_loads(self):
        content = load_content(self.dir)
        self.assertEqual(set(content.steps), {'permits', 'construction'})
        self.assertEqual(set(content.services), {'at/building-permit'})

    def test_missing_required_field(self):
        self.write('services/at/no-summary.yaml', "name: 'AT: X'\nstep: permits\n")
        self.assert_invalid('services/at/no-summary.yaml: "summary" is required')

    def test_too_long_summary(self):
        self.write('services/at/long.yaml', f"name: 'AT: X'\nstep: permits\nsummary: {'x' * 501}\n")
        self.assert_invalid('"summary" is 501 characters long (maximum 500)')

    def test_unknown_step(self):
        self.write('services/at/lost.yaml', "name: 'AT: X'\nstep: nowhere\nsummary: S\n")
        self.assert_invalid('step "nowhere" does not exist')

    def test_unknown_country_folder(self):
        self.write('services/de/x.yaml', "name: 'DE: X'\nstep: permits\nsummary: S\n")
        self.assert_invalid('folder "de" is not a lowercase country code')

    def test_unknown_phase_folder(self):
        self.write('steps/later/x.yaml', 'title: X\nsort_order: 1\n')
        self.assert_invalid('unknown phase folder "later"')

    def test_non_http_link(self):
        self.write('services/at/js.yaml', "name: 'AT: X'\nstep: permits\nsummary: S\nweb_link: javascript:alert(1)\n")
        self.assert_invalid('"web_link" must start with https://')

    def test_duplicate_step_key(self):
        self.write('steps/operation/permits.yaml', 'title: Again\nsort_order: 1\n')
        self.assert_invalid('a step "permits" already exists')

    def test_unknown_field_catches_typos(self):
        self.write('services/at/typo.yaml', "name: 'AT: X'\nstep: permits\nsumary: S\nsummary: S\n")
        self.assert_invalid('unknown field(s): sumary')

    def test_broken_yaml_reports_line(self):
        self.write('services/at/broken.yaml', "name: 'AT: X\nstep: permits\n")
        self.assert_invalid('services/at/broken.yaml (line')

    def test_bad_file_name(self):
        self.write('services/at/Bad_Name.yaml', "name: 'AT: X'\nstep: permits\nsummary: S\n")
        self.assert_invalid('file name must be lowercase words')

    def test_invalid_content_changes_nothing(self):
        self.write('services/at/lost.yaml', "name: 'AT: X'\nstep: nowhere\nsummary: S\n")
        with self.assertRaises(CommandError):
            call_command('sync_content', path=str(self.dir), stdout=StringIO())
        self.assertFalse(Service.objects.exists())


class SyncTests(ContentFilesMixin, TestCase):
    def test_creates_everything(self):
        report = self.sync()
        self.assertEqual(report.counts['services'], {'created': 1})
        service = Service.objects.get()
        self.assertEqual(service.source_key, 'at/building-permit')
        self.assertEqual(service.slug, 'at-building-permit')
        self.assertEqual(service.country.name, 'Austria')
        self.assertEqual(service.general_step.title, 'Permits')
        self.assertEqual(service.description, 'Details about the permit.\nSecond line.')
        self.assertEqual([p.slug for p in service.phases.all()], ['planning'])
        self.assertEqual(GeneralStep.objects.get(source_key='permits').phase.slug, 'planning')

    def test_second_run_changes_nothing(self):
        self.sync()
        report = self.sync()
        self.assertEqual(report.changes, [])
        self.assertEqual(report.counts['services'], {'unchanged': 1})

    def test_dry_run_writes_nothing(self):
        report = self.sync(dry_run=True)
        self.assertEqual(report.counts['services'], {'created': 1})
        self.assertFalse(Service.objects.exists())
        self.assertFalse(Country.objects.exists())

    def test_update_keeps_identity_slug_and_project_links(self):
        self.sync()
        service = Service.objects.get()
        initiator = Initiator.objects.create(first_name='A', last_name='B', email='a@example.com')
        project = Project.objects.create(initiator=initiator, name='P', current_phase=service.general_step.phase)
        application = ServiceApplication.objects.create(project=project, service=service)
        self.write('services/at/building-permit.yaml', """
            name: 'AT: Building permit (new title)'
            step: permits
            summary: Changed summary.
        """)
        report = self.sync()
        self.assertEqual(report.counts['services'], {'updated': 1})
        updated = Service.objects.get()
        self.assertEqual(updated.pk, service.pk)
        self.assertEqual(updated.slug, 'at-building-permit')
        self.assertEqual(updated.name, 'AT: Building permit (new title)')
        self.assertEqual(updated.description, '')  # removed from the file
        self.assertEqual(ServiceApplication.objects.get().service, updated)
        self.assertEqual(application.pk, ServiceApplication.objects.get().pk)

    def test_removed_service_is_deactivated_and_hidden(self):
        self.sync()
        self.remove('services/at/building-permit.yaml')
        report = self.sync()
        self.assertEqual(report.counts['services'], {'deactivated': 1})
        self.assertFalse(Service.objects.get().is_active)
        get_user_model().objects.create_user('m@example.com', password='pw')  # past first-run setup
        self.assertNotContains(self.client.get(reverse('catalog:service_list')), 'Building permit')
        # Adding the file back reactivates the same row.
        self.write('services/at/building-permit.yaml', "name: 'AT: Building permit'\nstep: permits\nsummary: S\n")
        self.sync()
        self.assertTrue(Service.objects.get().is_active)
        self.assertEqual(Service.objects.count(), 1)

    def test_active_false_deactivates(self):
        self.write('services/at/building-permit.yaml', "name: 'AT: X'\nstep: permits\nsummary: S\nactive: false\n")
        self.sync()
        self.assertFalse(Service.objects.get().is_active)

    def test_removed_step_is_deleted(self):
        self.sync()
        self.remove('steps/realisation/construction.yaml')
        report = self.sync()
        self.assertEqual(report.counts['steps'], {'deleted': 1, 'unchanged': 1})
        self.assertFalse(GeneralStep.objects.filter(source_key='construction').exists())

    def test_step_can_move_to_another_phase(self):
        self.sync()
        self.remove('steps/planning/permits.yaml')
        self.write('steps/operation/permits.yaml', 'title: Permits\nsort_order: 10\n')
        self.sync()
        self.assertEqual(GeneralStep.objects.get(source_key='permits').phase.slug, 'operation')
        self.assertEqual([p.slug for p in Service.objects.get().phases.all()], ['operation'])

    def test_extra_phases(self):
        self.write('services/at/building-permit.yaml', """
            name: 'AT: X'
            step: permits
            summary: S
            extra_phases: [operation]
        """)
        self.sync()
        self.assertEqual(sorted(p.slug for p in Service.objects.get().phases.all()), ['operation', 'planning'])

    def test_new_service_slug_is_unique(self):
        Service.objects.create(name='Old', slug='at-building-permit', summary='S')
        self.sync()
        self.assertEqual(Service.objects.get(source_key='at/building-permit').slug, 'at-building-permit-2')

    def test_command_output(self):
        out = StringIO()
        call_command('sync_content', path=str(self.dir), dry_run=True, stdout=out)
        self.assertIn('Dry run', out.getvalue())
        self.assertIn('services: 1 created', out.getvalue())


class TranslationContentTests(ContentFilesMixin, TestCase):
    def add_translations(self):
        self.write('services/at/building-permit.yaml', """
            name: 'AT: Building permit'
            step: permits
            summary: Apply for the building permit.
            web_link: https://example.org/permit
            de:
              name: 'AT: Baubewilligung'
              summary: Die Baubewilligung beantragen.
              input: Lageplan
        """)
        self.write('steps/planning/permits.yaml', """
            title: Permits
            sort_order: 10
            de:
              title: Genehmigungen
              reviewed: true
            fr:
              title: Autorisations
        """)

    def test_country_language_is_required_and_known(self):
        self.write('countries.yaml', "- code: AT\n  name: Austria\n- code: HR\n  name: Croatia\n  language: xx\n")
        with self.assertRaises(ContentError) as ctx:
            load_content(self.dir)
        errors = '\n'.join(ctx.exception.errors)
        self.assertIn('AT needs "language"', errors)
        self.assertIn('HR needs "language"', errors)

    def test_translations_are_loaded(self):
        self.add_translations()
        content = load_content(self.dir)
        self.assertEqual(content.languages, {'AT': 'de', 'HR': 'hr'})
        self.assertEqual(
            content.services['at/building-permit'].translations,
            {'de': {'name': 'AT: Baubewilligung', 'summary': 'Die Baubewilligung beantragen.',
                    'service_input': 'Lageplan'}},
        )
        self.assertEqual(set(content.steps['permits'].translations), {'de', 'fr'})

    def test_service_only_allows_the_country_language(self):
        self.write('services/at/other.yaml', "name: 'AT: X'\nstep: permits\nsummary: S\nit:\n  name: X\n")
        self.assert_invalid('services/at/other.yaml: no "it:" block allowed here (services of AT can only have "de:")')

    def test_english_block_is_rejected(self):
        self.write('steps/planning/other.yaml', "title: X\nsort_order: 1\nen:\n  title: Y\n")
        self.assert_invalid('English texts go in the main fields')

    def test_block_fields_are_checked(self):
        self.write('services/at/other.yaml', f"""
            name: 'AT: X'
            step: permits
            summary: S
            de:
              titel: X
              summary: {'x' * 501}
              reviewed: yes please
        """)
        with self.assertRaises(ContentError) as ctx:
            load_content(self.dir)
        errors = '\n'.join(ctx.exception.errors)
        self.assertIn('services/at/other.yaml [de]: unknown field(s): titel', errors)
        self.assertIn('services/at/other.yaml [de]: "summary" is 501 characters long', errors)
        self.assertIn('services/at/other.yaml [de]: "reviewed" must be true or false', errors)

    def test_sync_creates_updates_and_removes_translations(self):
        self.sync()
        self.assertEqual(Country.objects.get(code='AT').language, 'de')
        self.add_translations()
        report = self.sync()
        self.assertEqual(report.counts['translations'], {'created': 3})
        service = Service.objects.get(source_key='at/building-permit')
        de = service.translations.get(language='de')
        self.assertEqual((de.name, de.service_input, de.description, de.reviewed), ('AT: Baubewilligung', 'Lageplan', '', False))
        self.assertTrue(StepTranslation.objects.get(language='de').reviewed)

        self.assertEqual(self.sync().counts['translations'], {'unchanged': 3})

        self.write('steps/planning/permits.yaml', """
            title: Permits
            sort_order: 10
            de:
              title: Genehmigungen und Bewilligungen
              reviewed: true
        """)
        report = self.sync()
        self.assertEqual(report.counts['translations'], {'updated': 1, 'unchanged': 1, 'deleted': 1})
        self.assertIn('deleted: translations step permits [fr]', report.changes)
        self.assertEqual(
            list(StepTranslation.objects.values_list('language', 'title')), [('de', 'Genehmigungen und Bewilligungen')],
        )

    def test_dry_run_writes_no_translations(self):
        self.sync()
        self.add_translations()
        self.assertEqual(self.sync(dry_run=True).counts['translations'], {'created': 3})
        self.assertFalse(ServiceTranslation.objects.exists())
        self.assertFalse(StepTranslation.objects.exists())

    def test_admin_shows_translations_read_only(self):
        self.add_translations()
        self.sync()
        admin = get_user_model().objects.create_superuser('admin@example.com', password='pw')
        self.client.force_login(admin)
        service = Service.objects.get()
        response = self.client.get(reverse('admin:catalog_service_change', args=[service.pk]))
        self.assertContains(response, 'AT: Baubewilligung')
        self.assertNotContains(response, 'name="translations-0-name"')


class RepositoryContentTests(TestCase):
    """The real data/ folder must always be valid (runs in CI on every change)."""

    def test_repository_content_is_valid_and_syncs(self):
        content = load_content(CONTENT_DIR)
        self.assertGreaterEqual(len(content.services), 1)
        report = sync_content(content)
        self.assertEqual(Service.objects.filter(is_active=True).count(), len(content.services))
        self.assertEqual(report.warnings, [])


@override_settings(CONTENT_REPO_URL='https://github.com/example/guidebook/edit/main/data/')
class ContentAdminTests(ContentFilesMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.sync()
        admin = get_user_model().objects.create_superuser('admin@example.com', password='pw')
        self.client.force_login(admin)
        self.service = Service.objects.get()

    def test_service_is_view_only_with_github_link(self):
        response = self.client.get(reverse('admin:catalog_service_change', args=[self.service.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'https://github.com/example/guidebook/edit/main/data/services/at/building-permit.yaml')
        self.assertNotContains(response, 'name="_save"')

    def test_no_add_change_or_delete(self):
        self.assertEqual(self.client.get(reverse('admin:catalog_service_add')).status_code, 403)
        response = self.client.post(reverse('admin:catalog_service_change', args=[self.service.pk]), {'name': 'Hacked'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.get(reverse('admin:catalog_service_delete', args=[self.service.pk])).status_code, 403)
        self.assertEqual(self.client.get(reverse('admin:catalog_generalstep_add')).status_code, 403)
        self.assertEqual(self.client.get(reverse('admin:catalog_country_add')).status_code, 403)

    def test_step_link(self):
        step = GeneralStep.objects.get(source_key='permits')
        response = self.client.get(reverse('admin:catalog_generalstep_change', args=[step.pk]))
        self.assertContains(response, 'edit/main/data/steps/planning/permits.yaml')
