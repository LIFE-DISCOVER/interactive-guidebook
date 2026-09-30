import logging
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse, translate_url
from django.utils import translation
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.generic import FormView

from .forms import SetupForm
from .setup import setup_code, setup_required

logger = logging.getLogger(__name__)


def set_language_cookie(response, language):
    response.set_cookie(
        settings.LANGUAGE_COOKIE_NAME,
        language,
        max_age=settings.LANGUAGE_COOKIE_AGE,
        path=settings.LANGUAGE_COOKIE_PATH,
        domain=settings.LANGUAGE_COOKIE_DOMAIN,
        secure=settings.LANGUAGE_COOKIE_SECURE,
        httponly=settings.LANGUAGE_COOKIE_HTTPONLY,
        samesite=settings.LANGUAGE_COOKIE_SAMESITE,
    )


def translate_path(url, language):
    """Return ``url`` (a local path, query string kept) in ``language``.

    Falls back to the home page when the path cannot be resolved.
    """
    # Language prefixes only resolve while their language is active.
    current = translation.get_language_from_path(urlsplit(url).path) or translation.get_language()
    with translation.override(current):
        translated = translate_url(url, language)
    if translated == url and current != language:
        with translation.override(language):
            return reverse('home')
    return translated


def switch_language(request, language):
    """Language switcher: show the current page in another language.

    Remembers the choice in a cookie, and for logged-in users also as their
    preferred language.
    """
    if language not in dict(settings.LANGUAGES):
        raise Http404
    next_url = request.GET.get('next', '')
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        next_url = '/'
    response = redirect(translate_path(next_url, language))
    set_language_cookie(response, language)
    user = request.user
    if user.is_authenticated and user.language != language:
        user.language = language
        user.save(update_fields=['language'])
    return response


class GuidebookLoginView(LoginView):
    """Login that switches to the user's preferred language afterwards."""

    template_name = 'accounts/login.html'

    def form_valid(self, form):
        response = super().form_valid(form)
        language = form.get_user().language
        if language:
            response = redirect(translate_path(response.url, language))
            set_language_cookie(response, language)
        return response


class SetupView(FormView):
    """First-run onboarding: create the initial administrator account."""

    form_class = SetupForm
    template_name = 'accounts/setup.html'

    def dispatch(self, request, *args, **kwargs):
        if not setup_required():
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        logger.warning('First-run setup is pending. Setup code: %s', setup_code())
        return super().get(request, *args, **kwargs)

    def form_valid(self, form):
        with transaction.atomic():
            # Re-check inside the transaction so two simultaneous submissions
            # cannot both create an administrator.
            if not setup_required():
                raise Http404
            user = form.save()
        login(self.request, user, backend='django.contrib.auth.backends.ModelBackend')
        messages.success(
            self.request,
            _('Welcome, %(name)s! Your administrator account is ready. '
              'Create accounts for your managers in the Admin area.') % {'name': user.first_name},
        )
        return redirect('catalog:guidebook')
