from django.conf import settings
from django.core.signals import request_finished
from django.test.runner import DiscoverRunner
from django.utils import translation


def reset_language(**kwargs):
    translation.activate(settings.LANGUAGE_CODE)


class GuidebookTestRunner(DiscoverRunner):
    """Test runner that resets the active language after every test-client request.

    LocaleMiddleware activates the language of the requested URL (e.g. /de/...) and
    leaves it active afterwards, which would make later reverse() calls and English
    assertions depend on test order.
    """

    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        request_finished.connect(reset_language, dispatch_uid='guidebook-reset-language')

    def teardown_test_environment(self, **kwargs):
        request_finished.disconnect(dispatch_uid='guidebook-reset-language')
        super().teardown_test_environment(**kwargs)
