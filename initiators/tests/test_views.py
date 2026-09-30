from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from catalog.models import Phase, Service
from initiators.models import Initiator, Project, ServiceApplication


class InitiatorsTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user('manager@example.com', password='pw')
        cls.planning = Phase.objects.get(slug='planning')
        cls.realisation = Phase.objects.get(slug='realisation')
        cls.initiator = Initiator.objects.create(
            first_name='Anna', last_name='Berger', email='anna@example.com',
        )
        cls.project = Project.objects.create(
            initiator=cls.initiator, name='Solar Roof', current_phase=cls.planning,
        )
        cls.service = Service.objects.create(name='Permit help', slug='permit-help', summary='S')

    def setUp(self):
        self.client.force_login(self.user)

    def messages(self, response):
        return [str(m) for m in response.context['messages']]


class SuccessMessageTests(InitiatorsTestCase):
    def test_create_initiator(self):
        response = self.client.post(reverse('initiators:initiator_create'), {
            'first_name': 'Max', 'last_name': 'Huber', 'email': 'max@example.com',
        }, follow=True)
        self.assertIn('Initiator Max Huber was created.', self.messages(response))

    def test_update_initiator(self):
        response = self.client.post(reverse('initiators:initiator_update', args=[self.initiator.pk]), {
            'first_name': 'Anna', 'last_name': 'Berger', 'email': 'anna@example.com',
        }, follow=True)
        self.assertIn('Changes to Anna Berger were saved.', self.messages(response))

    def test_create_project(self):
        response = self.client.post(reverse('initiators:project_create', args=[self.initiator.pk]), {
            'name': 'Wind Farm', 'current_phase': self.planning.pk, 'status': 'active',
        }, follow=True)
        self.assertIn('Project "Wind Farm" was created.', self.messages(response))

    def test_update_project(self):
        response = self.client.post(reverse('projects:project_update', args=[self.project.pk]), {
            'name': 'Solar Roof 2', 'status': 'on_hold',
        }, follow=True)
        self.assertIn('Changes to "Solar Roof 2" were saved.', self.messages(response))


class PhaseChangeTests(InitiatorsTestCase):
    def test_change_phase_shows_message(self):
        response = self.client.post(reverse('projects:project_phase_change', args=[self.project.pk]), {
            'current_phase': self.realisation.pk,
        }, follow=True)
        self.assertIn('Project moved to the Realisation phase.', self.messages(response))
        self.assertEqual(self.project.phase_entries.count(), 2)

    def test_same_phase_is_rejected(self):
        response = self.client.post(reverse('projects:project_phase_change', args=[self.project.pk]), {
            'current_phase': self.planning.pk,
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'The project is already in the Planning phase.')
        self.assertEqual(self.project.phase_entries.count(), 1)


class ServiceApplicationTests(InitiatorsTestCase):
    def url(self):
        return reverse('projects:service_application_create', args=[self.project.pk])

    def test_add_service_shows_message(self):
        response = self.client.post(self.url(), {
            'service': self.service.pk, 'applied_on': '2026-09-30',
        }, follow=True)
        self.assertIn('Service "Permit help" was added to the project.', self.messages(response))

    def test_duplicate_service_shows_form_error(self):
        ServiceApplication.objects.create(project=self.project, service=self.service)
        response = self.client.post(self.url(), {
            'service': self.service.pk, 'applied_on': '2026-09-30',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'This service has already been applied to this project.')
        self.assertEqual(ServiceApplication.objects.count(), 1)

    def test_remove_service_shows_message(self):
        sa = ServiceApplication.objects.create(project=self.project, service=self.service)
        response = self.client.post(
            reverse('projects:service_application_delete', args=[self.project.pk, sa.pk]), follow=True,
        )
        self.assertIn('Service "Permit help" was removed from the project.', self.messages(response))
        self.assertFalse(ServiceApplication.objects.exists())


class ListAndEmptyStateTests(InitiatorsTestCase):
    def test_initiator_list_paginates(self):
        Initiator.objects.bulk_create(
            Initiator(first_name='X', last_name=f'Person {i:02d}', email=f'p{i}@example.com')
            for i in range(25)
        )
        response = self.client.get(reverse('initiators:initiator_list'))
        self.assertEqual(len(response.context['initiators']), 20)
        self.assertContains(response, 'Page 1 of 2')

    def test_project_list_empty_state_links_to_initiators(self):
        Project.objects.all().delete()
        response = self.client.get(reverse('projects:project_list'))
        self.assertContains(response, 'choose an initiator')

    def test_project_detail_empty_services_links_to_add(self):
        response = self.client.get(reverse('projects:project_detail', args=[self.project.pk]))
        self.assertContains(response, 'Add the first service')

    def test_nav_highlights_projects(self):
        response = self.client.get(reverse('projects:project_detail', args=[self.project.pk]))
        self.assertContains(response, 'aria-current="page">Projects</a>')


class ServiceDropdownCountryTests(InitiatorsTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        from catalog.models import Country
        cls.austria = Country.objects.create(code='AT', name='Austria')
        cls.germany = Country.objects.create(code='DE', name='Germany')
        cls.at_service = Service.objects.create(
            name='AT: Permit', slug='at-permit', summary='S', country=cls.austria,
        )
        cls.de_service = Service.objects.create(
            name='DE: Permit', slug='de-permit', summary='S', country=cls.germany,
        )

    def url(self):
        return reverse('projects:service_application_create', args=[self.project.pk])

    def service_choices(self):
        return set(self.client.get(self.url()).context['form'].fields['service'].queryset)

    def test_manager_sees_only_own_country(self):
        self.user.country = self.austria
        self.user.save()
        self.assertEqual(self.service_choices(), {self.at_service})

    def test_manager_without_country_sees_all(self):
        self.assertEqual(self.service_choices(), {self.at_service, self.de_service, self.service})

    def test_other_country_service_is_rejected(self):
        self.user.country = self.austria
        self.user.save()
        response = self.client.post(self.url(), {
            'service': self.de_service.pk, 'applied_on': '2026-09-30',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Select a valid choice')
        self.assertFalse(ServiceApplication.objects.exists())
