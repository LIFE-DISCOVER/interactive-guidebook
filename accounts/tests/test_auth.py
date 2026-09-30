from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from accounts.setup import setup_code
from catalog.models import Country

User = get_user_model()


class EmailLoginTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('Anna.Berger@Example.com', password='S3cure-pass!')

    def login(self, email, password='S3cure-pass!'):
        return self.client.post(reverse('accounts:login'), {'username': email, 'password': password})

    def test_email_is_stored_lowercase(self):
        self.assertEqual(self.user.email, 'anna.berger@example.com')

    def test_login_with_email(self):
        response = self.login('anna.berger@example.com')
        self.assertRedirects(response, reverse('catalog:service_list'), fetch_redirect_response=False)

    def test_login_is_case_insensitive(self):
        response = self.login('ANNA.BERGER@example.COM')
        self.assertRedirects(response, reverse('catalog:service_list'), fetch_redirect_response=False)

    def test_wrong_password_is_rejected(self):
        response = self.login('anna.berger@example.com', 'wrong')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_login_form_asks_for_email(self):
        response = self.client.get(reverse('accounts:login'))
        self.assertContains(response, 'Email address')

    def test_duplicate_email_differing_in_case_is_rejected_in_admin(self):
        admin = User.objects.create_superuser('admin@example.com', password='S3cure-pass!')
        self.client.force_login(admin)
        response = self.client.post(reverse('admin:accounts_customuser_add'), {
            'email': 'ANNA.BERGER@example.com',
            'usable_password': 'true',
            'password1': 'An0ther-pass!', 'password2': 'An0ther-pass!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'already exists')

    def test_admin_can_create_manager(self):
        admin = User.objects.create_superuser('admin@example.com', password='S3cure-pass!')
        self.client.force_login(admin)
        response = self.client.post(reverse('admin:accounts_customuser_add'), {
            'email': 'Max@Example.com', 'first_name': 'Max', 'last_name': 'Huber',
            'usable_password': 'true',
            'password1': 'An0ther-pass!', 'password2': 'An0ther-pass!',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(email='max@example.com', is_superuser=False).exists())

    def test_admin_user_list_and_change_pages(self):
        admin = User.objects.create_superuser('admin@example.com', password='S3cure-pass!')
        self.client.force_login(admin)
        self.assertEqual(self.client.get(reverse('admin:accounts_customuser_changelist')).status_code, 200)
        url = reverse('admin:accounts_customuser_change', args=[self.user.pk])
        self.assertEqual(self.client.get(url).status_code, 200)


class FirstRunSetupTests(TestCase):
    def valid_data(self, **overrides):
        data = {
            'setup_code': setup_code(),
            'first_name': 'Helga', 'last_name': 'Admin',
            'email': 'Helga@Example.com',
            'country': '',
            'password1': 'S3cure-pass!', 'password2': 'S3cure-pass!',
        }
        data.update(overrides)
        return data

    def test_redirects_to_setup_while_no_user_exists(self):
        for path in ['/', '/catalog/', '/accounts/login/', '/admin/']:
            response = self.client.get(path)
            self.assertRedirects(response, reverse('accounts:setup'), fetch_redirect_response=False)

    def test_static_files_are_not_redirected(self):
        response = self.client.get('/static/img/discover-logo-color.png')
        self.assertNotEqual(response.status_code, 302)

    def test_setup_page_renders(self):
        with self.assertLogs('accounts.views', 'WARNING') as logs:
            response = self.client.get(reverse('accounts:setup'))
        self.assertContains(response, 'Create administrator')
        self.assertIn(setup_code(), logs.output[0])

    def test_wrong_setup_code_is_rejected(self):
        response = self.client.post(reverse('accounts:setup'), self.valid_data(setup_code='0000-0000-0000'))
        self.assertContains(response, 'This setup code is not correct.')
        self.assertFalse(User.objects.exists())

    def test_mismatched_passwords_are_rejected(self):
        response = self.client.post(reverse('accounts:setup'), self.valid_data(password2='Different-pass1!'))
        self.assertContains(response, 'The two passwords do not match.')
        self.assertFalse(User.objects.exists())

    def test_weak_password_is_rejected(self):
        response = self.client.post(reverse('accounts:setup'), self.valid_data(password1='123', password2='123'))
        self.assertContains(response, 'too short')
        self.assertFalse(User.objects.exists())

    def test_setup_code_is_case_and_space_insensitive(self):
        code = ' ' + setup_code().lower() + ' '
        self.client.post(reverse('accounts:setup'), self.valid_data(setup_code=code))
        self.assertTrue(User.objects.exists())

    def test_successful_setup_creates_admin_and_logs_in(self):
        austria = Country.objects.create(code='AT', name='Austria')
        response = self.client.post(reverse('accounts:setup'), self.valid_data(country=austria.pk), follow=True)
        admin = User.objects.get()
        self.assertEqual(admin.email, 'helga@example.com')
        self.assertTrue(admin.is_superuser and admin.is_staff)
        self.assertEqual(admin.country, austria)
        self.assertTrue(admin.check_password('S3cure-pass!'))
        self.assertEqual(response.wsgi_request.user, admin)
        self.assertContains(response, 'Welcome, Helga!')

    def test_setup_is_gone_after_completion(self):
        User.objects.create_user('someone@example.com', password='pw')
        self.assertEqual(self.client.get(reverse('accounts:setup')).status_code, 404)
        response = self.client.post(reverse('accounts:setup'), self.valid_data())
        self.assertEqual(response.status_code, 404)
        self.assertEqual(User.objects.count(), 1)

    def test_setup_code_command(self):
        out = StringIO()
        call_command('setup_code', stdout=out)
        self.assertIn(setup_code(), out.getvalue())
        User.objects.create_user('someone@example.com', password='pw')
        out = StringIO()
        call_command('setup_code', stdout=out)
        self.assertIn('already complete', out.getvalue())


class EnsureAdminCommandTests(TestCase):
    def run_command(self, **env):
        from unittest import mock
        out, err = StringIO(), StringIO()
        with mock.patch.dict('os.environ', env, clear=False):
            call_command('ensure_admin', stdout=out, stderr=err)
        return out.getvalue(), err.getvalue()

    def test_creates_admin_on_first_launch(self):
        out, _ = self.run_command(DJANGO_SUPERUSER_EMAIL='Admin@Example.com', DJANGO_SUPERUSER_PASSWORD='S3cure-pass!')
        admin = User.objects.get()
        self.assertEqual(admin.email, 'admin@example.com')
        self.assertTrue(admin.is_superuser and admin.is_staff)
        self.assertTrue(admin.check_password('S3cure-pass!'))
        self.assertIn('first-run setup skipped', out)

    def test_setup_page_is_skipped_afterwards(self):
        self.run_command(DJANGO_SUPERUSER_EMAIL='admin@example.com', DJANGO_SUPERUSER_PASSWORD='S3cure-pass!')
        self.assertEqual(self.client.get(reverse('accounts:setup')).status_code, 404)
        projects = reverse('projects:project_list')
        self.assertRedirects(
            self.client.get(projects), f"{reverse('accounts:login')}?next={projects}", fetch_redirect_response=False,
        )

    def test_does_nothing_without_settings(self):
        out, err = self.run_command(DJANGO_SUPERUSER_EMAIL='', DJANGO_SUPERUSER_PASSWORD='')
        self.assertFalse(User.objects.exists())
        self.assertEqual(out + err, '')

    def test_requires_both_values(self):
        _, err = self.run_command(DJANGO_SUPERUSER_EMAIL='admin@example.com', DJANGO_SUPERUSER_PASSWORD='')
        self.assertIn('set both', err)
        self.assertFalse(User.objects.exists())

    def test_rejects_weak_password(self):
        _, err = self.run_command(DJANGO_SUPERUSER_EMAIL='admin@example.com', DJANGO_SUPERUSER_PASSWORD='123')
        self.assertIn('too short', err)
        self.assertFalse(User.objects.exists())

    def test_rejects_invalid_email(self):
        _, err = self.run_command(DJANGO_SUPERUSER_EMAIL='not-an-email', DJANGO_SUPERUSER_PASSWORD='S3cure-pass!')
        self.assertIn('valid email', err)
        self.assertFalse(User.objects.exists())

    def test_never_touches_existing_users(self):
        existing = User.objects.create_superuser('first@example.com', password='Original-pass1!')
        out, _ = self.run_command(DJANGO_SUPERUSER_EMAIL='first@example.com', DJANGO_SUPERUSER_PASSWORD='Other-pass1!')
        existing.refresh_from_db()
        self.assertTrue(existing.check_password('Original-pass1!'))
        self.assertEqual(User.objects.count(), 1)
        self.assertIn('ignored', out)
