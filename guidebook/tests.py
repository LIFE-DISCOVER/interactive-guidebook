from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
from django.views.defaults import server_error


class ErrorPageTests(TestCase):
    def test_404_page_for_logged_in_user(self):
        user = get_user_model().objects.create_user('manager@example.com', password='pw')
        self.client.force_login(user)
        response = self.client.get('/does-not-exist/')
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, '404.html')
        self.assertContains(response, 'Page not found', status_code=404)
        self.assertContains(response, 'Go to the Guidebook', status_code=404)

    def test_404_page_for_anonymous_user(self):
        get_user_model().objects.create_user('manager@example.com', password='pw')
        response = self.client.get('/does-not-exist/')
        self.assertContains(response, 'Page not found', status_code=404)

    def test_500_page(self):
        response = server_error(RequestFactory().get('/'))
        self.assertEqual(response.status_code, 500)
        self.assertIn(b'Something went wrong', response.content)


class LanguageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user('manager@example.com', password='S3cure-pass!')

    # Detection and redirects

    def test_root_redirects_to_english_by_default(self):
        response = self.client.get('/')
        self.assertRedirects(response, '/en/', fetch_redirect_response=False)

    def test_root_follows_browser_language(self):
        response = self.client.get('/', headers={'accept-language': 'de-AT,de;q=0.9,en;q=0.5'})
        self.assertRedirects(response, '/de/', fetch_redirect_response=False)

    def test_cookie_wins_over_browser_language(self):
        self.client.cookies['django_language'] = 'hr'
        response = self.client.get('/', headers={'accept-language': 'de'})
        self.assertRedirects(response, '/hr/', fetch_redirect_response=False)

    def test_old_links_keep_their_query(self):
        response = self.client.get('/catalog/?country=HR&phase=planning')
        self.assertRedirects(response, '/en/catalog/?country=HR&phase=planning', fetch_redirect_response=False)

    def test_prefixed_pages_render_in_their_language(self):
        response = self.client.get('/bg/catalog/')
        self.assertContains(response, '<html lang="bg">')
        # Django ships German for "email address", so the pipeline is visible
        # before our own translations exist.
        response = self.client.get('/de/accounts/login/')
        self.assertContains(response, 'E-Mail-Adresse')

    # Switcher

    def test_switcher_keeps_page_and_filters(self):
        response = self.client.get('/language/de/', {'next': '/en/catalog/?country=HR&phase=planning'})
        self.assertRedirects(response, '/de/catalog/?country=HR&phase=planning', fetch_redirect_response=False)
        self.assertEqual(response.cookies['django_language'].value, 'de')

    def test_switcher_saves_preference_for_logged_in_user(self):
        self.client.force_login(self.user)
        self.client.get('/language/it/', {'next': '/en/projects/'})
        self.user.refresh_from_db()
        self.assertEqual(self.user.language, 'it')

    def test_switcher_rejects_unknown_language(self):
        self.assertEqual(self.client.get('/language/xx/', {'next': '/en/'}).status_code, 404)

    def test_switcher_ignores_external_next(self):
        response = self.client.get('/language/fr/', {'next': 'https://evil.example.com/'})
        self.assertRedirects(response, '/fr/', fetch_redirect_response=False)

    def test_switcher_falls_back_to_home_for_unknown_pages(self):
        response = self.client.get('/language/fr/', {'next': '/en/no-such-page/'})
        self.assertRedirects(response, '/fr/', fetch_redirect_response=False)

    def test_menu_and_footer_list_all_languages(self):
        response = self.client.get('/en/catalog/')
        for name in ['English', 'Deutsch', 'Français', 'Italiano', 'Hrvatski', 'Български']:
            self.assertContains(response, f'>{name}</a>', count=2)  # menu + footer
        self.assertContains(response, 'hreflang="de" href="http://testserver/de/catalog/"')

    # Preferred language at login

    def test_login_switches_to_preferred_language(self):
        self.user.language = 'fr'
        self.user.save()
        response = self.client.post('/en/accounts/login/?next=/en/projects/', {
            'username': 'manager@example.com', 'password': 'S3cure-pass!',
        })
        self.assertRedirects(response, '/fr/projects/', fetch_redirect_response=False)
        self.assertEqual(response.cookies['django_language'].value, 'fr')

    def test_login_without_preference_keeps_language(self):
        response = self.client.post('/de/accounts/login/', {
            'username': 'manager@example.com', 'password': 'S3cure-pass!',
        })
        self.assertRedirects(response, '/de/catalog/', fetch_redirect_response=False)


class SetupLanguageTests(TestCase):
    """While no user exists, the setup page works in every language."""

    def test_setup_redirect_keeps_language(self):
        response = self.client.get('/it/catalog/')
        self.assertRedirects(response, '/it/accounts/setup/', fetch_redirect_response=False)

    def test_switcher_works_during_setup(self):
        response = self.client.get('/language/hr/', {'next': '/en/accounts/setup/'})
        self.assertRedirects(response, '/hr/accounts/setup/', fetch_redirect_response=False)


class FooterSourceLinkTests(TestCase):
    def setUp(self):
        get_user_model().objects.create_user('manager@example.com', password='pw')  # past first-run setup

    def test_footer_links_to_source_code(self):
        response = self.client.get('/de/')
        self.assertContains(
            response,
            '<a href="https://github.com/LIFE-DISCOVER/interactive-guidebook" target="_blank" rel="noopener">'
            'Quellcode auf GitHub</a>',
            html=True,
        )

    @override_settings(SOURCE_CODE_URL='')
    def test_link_hidden_when_not_configured(self):
        self.assertNotContains(self.client.get('/en/'), 'Source code on GitHub')
