"""First-run setup: create the initial administrator while no user exists."""
from django.contrib.auth import get_user_model
from django.utils.crypto import constant_time_compare, salted_hmac


def setup_required():
    return not get_user_model().objects.exists()


def setup_code():
    """One-time code protecting the setup page, derived from SECRET_KEY.

    Only someone with access to the server (logs, shell or environment) can
    obtain it, so a stranger cannot claim the administrator account of a
    freshly deployed instance.
    """
    digest = salted_hmac('accounts.setup', 'first-run-setup').hexdigest()[:12].upper()
    return f'{digest[:4]}-{digest[4:8]}-{digest[8:]}'


def check_setup_code(value):
    normalized = value.strip().upper().replace(' ', '')
    return constant_time_compare(normalized, setup_code())
