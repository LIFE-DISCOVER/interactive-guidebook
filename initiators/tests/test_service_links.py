from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from catalog.models import Phase, Service
from initiators.models import Initiator, Project, ServiceApplication, ServiceLink


class ServiceLinkTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager = get_user_model().objects.create_user(
            'manager@example.com', password='pw', first_name='Anna', last_name='Berger',
        )
        cls.initiator = Initiator.objects.create(first_name='Max', last_name='Huber', email='max@example.com')
        cls.project = Project.objects.create(
            initiator=cls.initiator, name='Solar Roof', current_phase=Phase.objects.get(slug='planning'),
        )
        cls.service = Service.objects.create(
            name='Permit help', slug='permit-help', summary='Helps with permits',
            description='Full description of the permit service.', web_link='https://example.org/permits',
        )
        cls.application = ServiceApplication.objects.create(project=cls.project, service=cls.service)

    def create_url(self, application=None):
        application = application or self.application
        return reverse('projects:service_link_create', args=[application.project_id, application.pk])

    def make_link(self, **kwargs):
        return ServiceLink.objects.create(application=self.application, created_by=self.manager, **kwargs)

    def public_url(self, link):
        return reverse('service_link', args=[link.token])


class ManagerLinkTests(ServiceLinkTestCase):
    def setUp(self):
        self.client.force_login(self.manager)

    def test_create_requires_login(self):
        self.client.logout()
        response = self.client.post(self.create_url())
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response.url)
        self.assertFalse(ServiceLink.objects.exists())

    def test_create_link_without_message(self):
        response = self.client.post(self.create_url(), {'message': ''})
        self.assertRedirects(
            response, reverse('projects:project_detail', args=[self.project.pk]) + f'#service-{self.application.pk}',
            fetch_redirect_response=False,
        )
        link = ServiceLink.objects.get()
        self.assertTrue(link.is_active)
        self.assertFalse(link.is_used)
        self.assertEqual(link.created_by, self.manager)
        self.assertEqual(link.message, '')
        self.assertGreaterEqual(len(link.token), 40)

    def test_create_link_with_message(self):
        self.client.post(self.create_url(), {'message': 'Please bring the roof plans.'})
        self.assertEqual(ServiceLink.objects.get().message, 'Please bring the roof plans.')

    def test_too_long_message_is_rejected(self):
        response = self.client.post(self.create_url(), {'message': 'x' * 2001}, follow=True)
        self.assertFalse(ServiceLink.objects.exists())
        self.assertContains(response, '2000')

    def test_new_link_replaces_unused_link_but_keeps_used_ones(self):
        used = self.make_link(note='Done', submitted_at='2026-09-01T10:00:00Z')
        unused = self.make_link()
        self.client.post(self.create_url(), {'message': 'Second try'})
        used.refresh_from_db(); unused.refresh_from_db()
        self.assertTrue(used.is_active)
        self.assertFalse(unused.is_active)
        self.assertEqual(self.application.links.filter(is_active=True, submitted_at__isnull=True).count(), 1)

    def test_revoke(self):
        link = self.make_link()
        self.client.post(reverse('projects:service_link_revoke', args=[self.project.pk, self.application.pk, link.pk]))
        link.refresh_from_db()
        self.assertFalse(link.is_active)
        self.assertEqual(self.client.get(self.public_url(link)).status_code, 404)

    def test_wrong_project_is_404(self):
        other = Project.objects.create(initiator=self.initiator, name='Other', current_phase=self.project.current_phase)
        url = reverse('projects:service_link_create', args=[other.pk, self.application.pk])
        self.assertEqual(self.client.post(url).status_code, 404)

    def test_project_page_shows_link_tools_and_notes(self):
        link = self.make_link(message='Bring plans')
        self.make_link(note='We sent the plans.', submitted_at='2026-09-01T10:00:00Z', is_active=True)
        response = self.client.get(reverse('projects:project_detail', args=[self.project.pk]))
        self.assertContains(response, f'value="http://testserver/share/{link.token}/"')
        self.assertContains(response, 'data-copy=')
        self.assertContains(response, 'href="mailto:max%40example.com?subject=')
        self.assertContains(response, 'Bring plans')
        self.assertContains(response, 'We sent the plans.')

    def test_project_page_offers_create_when_no_link(self):
        response = self.client.get(reverse('projects:project_detail', args=[self.project.pk]))
        self.assertContains(response, 'Create link for initiator')

    def test_deleting_application_removes_links(self):
        self.make_link()
        self.client.post(reverse('projects:service_application_delete', args=[self.project.pk, self.application.pk]))
        self.assertFalse(ServiceLink.objects.exists())


class PublicLinkTests(ServiceLinkTestCase):
    def test_unknown_token_is_404(self):
        self.assertEqual(self.client.get('/en/share/not-a-real-token/').status_code, 404)

    def test_open_link_shows_service_and_form(self):
        link = self.make_link()
        response = self.client.get(self.public_url(link))
        self.assertContains(response, 'Permit help')
        self.assertContains(response, 'Full description of the permit service.')
        self.assertContains(response, 'href="https://example.org/permits"')
        self.assertContains(response, 'rel="noopener noreferrer"')
        self.assertContains(response, 'name="note"')
        self.assertContains(response, 'Solar Roof')
        self.assertNotContains(response, 'max@example.com')

    def test_privacy_headers(self):
        response = self.client.get(self.public_url(self.make_link()))
        self.assertEqual(response['X-Robots-Tag'], 'noindex, nofollow')
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        # Not 'no-referrer': that makes browsers send "Origin: null" and the note form fails CSRF.
        self.assertEqual(response['Referrer-Policy'], 'same-origin')
        self.assertContains(response, '<meta name="robots" content="noindex, nofollow">')

    def test_personal_message_with_sender(self):
        link = self.make_link(message='Please bring the roof plans.')
        response = self.client.get(self.public_url(link))
        self.assertContains(response, 'Message from Anna Berger')
        self.assertContains(response, 'Please bring the roof plans.')

    def test_message_without_sender_name(self):
        link = self.make_link(message='Hello')
        link.created_by = None
        link.save()
        self.assertContains(self.client.get(self.public_url(link)), 'Message from your energy agency')

    def test_message_html_is_escaped(self):
        link = self.make_link(message='<script>alert(1)</script>')
        response = self.client.get(self.public_url(link))
        self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertContains(response, '&lt;script&gt;')

    def test_no_message_no_box(self):
        self.assertNotContains(self.client.get(self.public_url(self.make_link())), 'link-message')

    def test_unsafe_official_link_is_hidden(self):
        self.service.web_link = 'javascript:alert(1)'
        self.service.save()
        self.assertNotContains(self.client.get(self.public_url(self.make_link())), 'javascript:')

    def test_submit_note_once(self):
        link = self.make_link(message='Please bring the roof plans.')
        response = self.client.post(self.public_url(link), {'note': 'Plans are attached to my email.'}, follow=True)
        link.refresh_from_db()
        self.assertEqual(link.note, 'Plans are attached to my email.')
        self.assertIsNotNone(link.submitted_at)
        self.assertContains(response, 'Thank you! Your note has been sent.')
        # Read-only afterwards, message still visible
        self.assertNotContains(response, 'name="note"')
        self.assertContains(response, 'Plans are attached to my email.')
        self.assertContains(response, 'Please bring the roof plans.')

    def test_second_submission_does_not_overwrite(self):
        link = self.make_link()
        self.client.post(self.public_url(link), {'note': 'First'})
        response = self.client.post(self.public_url(link), {'note': 'Second'})
        link.refresh_from_db()
        self.assertEqual(link.note, 'First')
        self.assertContains(response, 'First')
        self.assertNotContains(response, 'name="note"')

    def test_empty_and_too_long_notes_are_rejected(self):
        link = self.make_link()
        for note in ['', 'x' * 5001]:
            response = self.client.post(self.public_url(link), {'note': note})
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'errorlist')
        link.refresh_from_db()
        self.assertFalse(link.is_used)

    def test_shared_link_without_language_follows_browser(self):
        link = self.make_link()
        self.assertEqual(link.get_public_path(), f'/share/{link.token}/')
        response = self.client.get(link.get_public_path(), headers={'accept-language': 'de'})
        self.assertRedirects(response, f'/de/share/{link.token}/', fetch_redirect_response=False)

    def test_link_page_is_translated(self):
        link = self.make_link()
        response = self.client.get(f'/de/share/{link.token}/')
        self.assertContains(response, '<html lang="de">')
