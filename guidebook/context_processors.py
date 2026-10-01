from urllib.parse import urlencode

from django.conf import settings
from django.urls import reverse
from django.utils import translation


def languages(request):
    """Links for the language switcher and hreflang alternates."""
    from accounts.views import translate_path

    current = translation.get_language()
    path = request.get_full_path()
    links = []
    for code, name in settings.LANGUAGES:
        links.append({
            'code': code,
            'name': name,
            'is_current': code == current,
            'switch_url': reverse('switch_language', args=[code]) + '?' + urlencode({'next': path}),
            'alternate_url': request.build_absolute_uri(translate_path(path, code)),
        })
    return {'language_links': links, 'current_language': current}


def site_links(request):
    """Links shown on every page."""
    return {'source_code_url': settings.SOURCE_CODE_URL}
