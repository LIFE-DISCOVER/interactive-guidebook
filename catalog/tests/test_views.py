from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from catalog.models import Phase, Service


class ServiceListViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user('manager@example.com', password='pw')
        planning = Phase.objects.get(slug='planning')
        for i in range(30):
            service = Service.objects.create(
                name=f'Service {i:02d}', slug=f'service-{i:02d}', summary='Summary',
            )
            if i < 5:
                service.servicephase_set.create(phase=planning)

    def setUp(self):
        self.client.force_login(self.user)

    def test_paginates_services(self):
        response = self.client.get(reverse('catalog:service_list'))
        self.assertEqual(len(response.context['services']), 24)
        self.assertContains(response, 'Page 1 of 2')
        self.assertContains(response, '30 services')

    def test_second_page(self):
        response = self.client.get(reverse('catalog:service_list'), {'page': 2})
        self.assertEqual(len(response.context['services']), 6)

    def test_pagination_links_keep_filters(self):
        response = self.client.get(reverse('catalog:service_list'), {'q': 'Service'})
        self.assertContains(response, 'href="?q=Service&amp;page=2"')

    def test_phase_filter(self):
        response = self.client.get(reverse('catalog:service_list'), {'phase': 'planning'})
        self.assertEqual(response.context['paginator'].count, 5)
        self.assertNotContains(response, 'Page 1 of')

    def test_empty_search_shows_empty_state(self):
        response = self.client.get(reverse('catalog:service_list'), {'q': 'nothing-matches'})
        self.assertContains(response, 'No services found matching')
        self.assertContains(response, 'Clear filters')

    def test_nav_highlights_services(self):
        response = self.client.get(reverse('catalog:service_list'))
        self.assertContains(response, 'class="active" aria-current="page">Services</a>', html=False)
        self.assertNotContains(response, 'aria-current="page">Guidebook')

    def test_nav_highlights_guidebook(self):
        response = self.client.get(reverse('catalog:guidebook'))
        self.assertContains(response, 'aria-current="page">Guidebook</a>')
        self.assertNotContains(response, 'aria-current="page">Services')


class PublicCatalogTests(TestCase):
    """The service catalog is public; everything else still requires login."""

    @classmethod
    def setUpTestData(cls):
        # An existing account, so the first-run setup redirect does not apply.
        get_user_model().objects.create_user('manager@example.com', password='pw')
        cls.service = Service.objects.create(name='Permit help', slug='permit-help', summary='Helps with permits')
        cls.inactive = Service.objects.create(name='Retired', slug='retired', summary='S', is_active=False)

    def test_anonymous_can_browse_list(self):
        response = self.client.get(reverse('catalog:service_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Permit help')
        self.assertNotContains(response, 'Retired')

    def test_anonymous_can_view_detail(self):
        response = self.client.get(reverse('catalog:service_detail', args=['permit-help']))
        self.assertContains(response, 'Helps with permits')

    def test_inactive_service_is_not_reachable(self):
        response = self.client.get(reverse('catalog:service_detail', args=['retired']))
        self.assertEqual(response.status_code, 404)

    def test_other_pages_still_require_login(self):
        for name in ['initiators:initiator_list', 'projects:project_list']:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 302, name)
            self.assertTrue(response.url.startswith(reverse('accounts:login')), name)
        response = self.client.post(reverse('catalog:set_country'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse('accounts:login')))

    def test_nav_for_anonymous_shows_only_public_links(self):
        response = self.client.get(reverse('catalog:service_list'))
        self.assertContains(response, 'aria-current="page">Services</a>')
        self.assertContains(response, '>Login</a>')
        self.assertNotContains(response, reverse('initiators:initiator_list'))
        self.assertNotContains(response, reverse('projects:project_list'))
        self.assertContains(response, f'href="{reverse("catalog:guidebook")}"')

    def test_nav_for_logged_in_user_shows_all_links(self):
        self.client.force_login(get_user_model().objects.get())
        response = self.client.get(reverse('catalog:service_list'))
        for name in ['catalog:guidebook', 'initiators:initiator_list', 'projects:project_list']:
            self.assertContains(response, f'href="{reverse(name)}"')


class CountryFilterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from catalog.models import Country, GeneralStep
        cls.austria = Country.objects.create(code='AT', name='Austria')
        cls.italy = Country.objects.create(code='IT', name='Italy')
        planning = Phase.objects.get(slug='planning')
        cls.step = GeneralStep.objects.create(title='Permits', phase=planning, sort_order=1)
        cls.at_service = Service.objects.create(
            name='Vienna permit', slug='vienna-permit', summary='S', country=cls.austria, general_step=cls.step,
        )
        cls.it_service = Service.objects.create(
            name='Rome permit', slug='rome-permit', summary='S', country=cls.italy, general_step=cls.step,
        )
        cls.manager = get_user_model().objects.create_user(
            'manager@example.com', password='pw', country=cls.austria,
        )

    def names(self, response, key='services'):
        return {s.name for s in response.context[key]}

    def guidebook_names(self, response):
        return {svc.name for pd in response.context['phase_data'] for item in pd['steps'] for svc in item['services']}

    # Service list

    def test_anonymous_sees_all_countries_by_default(self):
        response = self.client.get(reverse('catalog:service_list'))
        self.assertEqual(self.names(response), {'Vienna permit', 'Rome permit'})
        self.assertContains(response, 'badge-country')

    def test_anonymous_can_filter_by_country(self):
        response = self.client.get(reverse('catalog:service_list'), {'country': 'it'})
        self.assertEqual(self.names(response), {'Rome permit'})
        self.assertContains(response, '1 service in Italy')
        self.assertContains(response, '<option value="IT" selected>Italy</option>', html=True)

    def test_unknown_country_shows_all(self):
        response = self.client.get(reverse('catalog:service_list'), {'country': 'XX'})
        self.assertEqual(self.names(response), {'Vienna permit', 'Rome permit'})

    def test_manager_defaults_to_own_country(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse('catalog:service_list'))
        self.assertEqual(self.names(response), {'Vienna permit'})

    def test_manager_can_switch_country_or_show_all(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse('catalog:service_list'), {'country': 'IT'})
        self.assertEqual(self.names(response), {'Rome permit'})
        response = self.client.get(reverse('catalog:service_list'), {'country': 'all'})
        self.assertEqual(self.names(response), {'Vienna permit', 'Rome permit'})

    def test_phase_tabs_keep_country(self):
        response = self.client.get(reverse('catalog:service_list'), {'country': 'AT'})
        self.assertContains(response, 'href="?country=AT&amp;phase=planning"')

    # Guidebook

    def test_guidebook_is_public(self):
        response = self.client.get(reverse('catalog:guidebook'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.guidebook_names(response), {'Vienna permit', 'Rome permit'})
        self.assertContains(response, 'Select your country')
        self.assertNotContains(response, 'my default')

    def test_guidebook_country_filter(self):
        response = self.client.get(reverse('catalog:guidebook'), {'country': 'AT'})
        self.assertEqual(self.guidebook_names(response), {'Vienna permit'})
        self.assertContains(response, 'Showing services for <strong>Austria</strong>', html=False)

    def test_guidebook_manager_defaults_to_own_country(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse('catalog:guidebook'))
        self.assertEqual(self.guidebook_names(response), {'Vienna permit'})
        self.assertNotContains(response, 'my default')

    def test_manager_can_save_other_country_as_default(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse('catalog:guidebook'), {'country': 'IT'})
        self.assertContains(response, 'Make Italy my default')
        response = self.client.post(reverse('catalog:set_country'), {'country_code': 'IT'}, follow=True)
        self.manager.refresh_from_db()
        self.assertEqual(self.manager.country, self.italy)
        self.assertContains(response, 'Italy is now your default country.')
        self.assertEqual(self.guidebook_names(response), {'Rome permit'})


class ServiceDetailFieldsTests(TestCase):
    """The service page shows the official link and all descriptive fields."""

    @classmethod
    def setUpTestData(cls):
        get_user_model().objects.create_user('manager@example.com', password='pw')  # past first-run setup
        cls.service = Service.objects.create(
            name='AT: Permit', slug='at-permit', summary='Short summary',
            description='Longer description',
            web_link='https://example.org/permit.pdf',
            stakeholder='City building authority',
            service_input='Site plan\nConstruction plan',
            result='Permit',
            remaining_hurdles='Sophisticated',
        )

    def get(self):
        return self.client.get(reverse('catalog:service_detail', args=['at-permit']))

    def test_shows_official_link_and_all_fields(self):
        response = self.get()
        self.assertContains(response, 'href="https://example.org/permit.pdf"')
        self.assertContains(response, 'rel="noopener noreferrer"')
        for label, value in [
            ('Offered by', 'City building authority'),
            ('What the initiator needs to provide', 'Site plan<br>Construction plan'),
            ('Result', 'Permit'),
            ('Remaining hurdles', 'Sophisticated'),
        ]:
            self.assertContains(response, label)
            self.assertContains(response, value)

    def test_empty_fields_are_hidden(self):
        Service.objects.filter(pk=self.service.pk).update(
            web_link='', stakeholder='', service_input='', result='', remaining_hurdles='',
        )
        response = self.get()
        self.assertNotContains(response, 'service-facts')
        self.assertNotContains(response, 'Official link')

    def test_unsafe_link_is_not_rendered(self):
        Service.objects.filter(pk=self.service.pk).update(web_link='javascript:alert(1)')
        self.assertNotContains(self.get(), 'javascript:')

    def test_fields_are_translated_labels(self):
        response = self.client.get('/de/catalog/at-permit/')
        self.assertContains(response, 'Offizieller Link')
