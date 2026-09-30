from django.conf import settings
from django.shortcuts import redirect
from django.urls import Resolver404, resolve, reverse

from .setup import setup_required

# Reachable while setup is pending (the language switcher works on the setup page).
SETUP_ALLOWED_VIEWS = {'accounts:setup', 'switch_language'}


class FirstRunSetupMiddleware:
    """Send every request to the setup page until the first user exists."""

    def __init__(self, get_response):
        self.get_response = get_response
        # Once a user exists, stop querying the database on every request.
        self.setup_done = False

    def __call__(self, request):
        if not self.setup_done:
            if not setup_required():
                self.setup_done = True
            elif not self.is_allowed(request):
                return redirect(reverse('accounts:setup'))
        return self.get_response(request)

    @staticmethod
    def is_allowed(request):
        if request.path.startswith('/' + settings.STATIC_URL.lstrip('/')):
            return True
        try:
            return resolve(request.path_info).view_name in SETUP_ALLOWED_VIEWS
        except Resolver404:
            return False
