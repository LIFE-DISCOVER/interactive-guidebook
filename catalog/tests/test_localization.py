from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from catalog.models import Country, GeneralStep, Phase, Service, ServiceTranslation, StepTranslation
from initiators.models import Initiator, Project, ServiceApplication, ServiceLink


class LocalizationTestCase(TestCase):
    """An Austrian service with a German translation, and a step translated into German."""

    @classmethod
    def setUpTestData(cls):
        cls.manager = get_user_model().objects.create_user('manager@example.com', password='pw')
        austria = Country.objects.create(code='AT', name='Austria', language='de')
        cls.step = GeneralStep.objects.create(
            title='Permits', description='Get the permits.', phase=Phase.objects.get(slug='planning'),
        )
        cls.step_de = StepTranslation.objects.create(step=cls.step, language='de', title='Genehmigungen')
        cls.service = Service.objects.create(
            name='AT: Building permit', slug='at-building-permit', summary='Apply for the permit.',
            description='English description.', result='Permit', country=austria, general_step=cls.step,
        )
        cls.service_de = ServiceTranslation.objects.create(
            service=cls.service, language='de', name='AT: Baubewilligung',
            summary='Die Baubewilligung beantragen.', result='Bewilligung',
        )

    def detail(self, language='en', **params):
        return self.client.get(f'/{language}/catalog/at-building-permit/', params)


class ServicePageTests(LocalizationTestCase):
    def test_local_interface_shows_translation(self):
        response = self.detail('de')
        self.assertContains(response, '<h1 lang="de">AT: Baubewilligung</h1>', html=True)
        self.assertContains(response, 'Die Baubewilligung beantragen.')
        self.assertContains(response, 'Bewilligung')
        self.assertNotContains(response, 'Apply for the permit.')

    def test_missing_field_falls_back_to_english(self):
        self.assertContains(self.detail('de'), 'English description.')

    def test_other_interface_language_shows_english(self):
        response = self.detail('fr')
        self.assertContains(response, 'AT: Building permit')
        self.assertNotContains(response, 'Baubewilligung')

    def test_switch_between_english_and_local_language(self):
        response = self.detail('en')
        self.assertContains(response, '<a href="?text=de" lang="de" hreflang="de">Deutsch</a>', html=True)
        self.assertContains(self.detail('en', text='de'), 'AT: Baubewilligung')
        response = self.detail('de', text='en')
        self.assertContains(response, 'Apply for the permit.')
        self.assertContains(response, '<a href="?text=de" lang="de" hreflang="de">Deutsch</a>', html=True)

    def test_unknown_text_language_is_ignored(self):
        self.assertContains(self.detail('en', text='it'), 'AT: Building permit')

    def test_no_switch_without_translation(self):
        self.service_de.delete()
        self.assertNotContains(self.detail('de'), 'text-language-switch')

    def test_draft_note_until_reviewed(self):
        self.assertContains(self.detail('de'), 'draft-translation-note')
        self.assertNotContains(self.detail('en'), 'draft-translation-note')
        ServiceTranslation.objects.update(reviewed=True)
        self.assertNotContains(self.detail('de'), 'draft-translation-note')


class ListAndGuidebookTests(LocalizationTestCase):
    def test_catalog_list_is_localized(self):
        response = self.client.get('/de/catalog/')
        self.assertContains(response, 'AT: Baubewilligung')
        self.assertContains(self.client.get('/it/catalog/'), 'AT: Building permit')

    def test_search_finds_local_terms_in_that_language(self):
        response = self.client.get('/de/catalog/', {'q': 'Baubewilligung'})
        self.assertEqual(response.context['paginator'].count, 1)
        response = self.client.get('/de/catalog/', {'q': 'permit'})
        self.assertEqual(response.context['paginator'].count, 1)
        response = self.client.get('/fr/catalog/', {'q': 'Baubewilligung'})
        self.assertEqual(response.context['paginator'].count, 0)

    def test_guidebook_shows_translated_steps_and_services(self):
        response = self.client.get('/de/catalog/guidebook/', {'country': 'AT'})
        self.assertContains(response, 'Genehmigungen')
        self.assertContains(response, 'Get the permits.')  # no German description: English
        self.assertContains(response, 'AT: Baubewilligung')
        self.assertContains(response, 'draft-translation-note')

    def test_guidebook_in_english_has_no_draft_note(self):
        response = self.client.get('/en/catalog/guidebook/', {'country': 'AT'})
        self.assertContains(response, 'Permits')
        self.assertNotContains(response, 'draft-translation-note')

    def test_guidebook_query_count_does_not_grow_per_service(self):
        for i in range(5):
            service = Service.objects.create(
                name=f'AT: S{i}', slug=f's{i}', summary='S', country=self.service.country, general_step=self.step,
            )
            ServiceTranslation.objects.create(service=service, language='de', name=f'AT: D{i}')
        self.client.get('/de/catalog/guidebook/')
        with self.assertNumQueries(7):
            self.client.get('/de/catalog/guidebook/', {'country': 'AT'})


class InitiatorPagesTests(LocalizationTestCase):
    def setUp(self):
        initiator = Initiator.objects.create(first_name='Max', last_name='Huber', email='max@example.com')
        self.project = Project.objects.create(
            initiator=initiator, name='Solar Roof', current_phase=Phase.objects.get(slug='planning'),
        )
        self.application = ServiceApplication.objects.create(project=self.project, service=self.service)

    def test_project_page_shows_localized_service_name(self):
        self.client.force_login(self.manager)
        response = self.client.get(f'/de/projects/{self.project.pk}/')
        self.assertContains(response, 'AT: Baubewilligung')

    def test_link_page_shows_localized_text_with_switch(self):
        link = ServiceLink.objects.create(application=self.application, created_by=self.manager)
        url = reverse('service_link', args=[link.token])
        response = self.client.get(f'/de{url[3:]}')
        self.assertContains(response, 'Die Baubewilligung beantragen.')
        self.assertContains(response, 'text-language-switch')
        response = self.client.get(f'/de{url[3:]}', {'text': 'en'})
        self.assertContains(response, 'Apply for the permit.')


class PhaseLabelTests(LocalizationTestCase):
    def test_phase_badges_follow_interface_language(self):
        self.service.servicephase_set.create(phase=Phase.objects.get(slug='planning'))
        self.assertContains(self.detail('de'), '>Planung</span>')
        self.assertContains(self.detail('fr'), '>Planification</span>')
        self.assertContains(self.detail('en'), '>Planning</span>')
        self.assertContains(self.client.get('/bg/catalog/guidebook/'), 'Планиране')
