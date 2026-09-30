"""Link existing steps and services to their content files (data/steps, data/services).

Keys are derived from the step title and the service name exactly like the one-time export
that created the files, so existing rows keep their primary keys, URLs and project links.
The derivation is copied here (not imported) so this migration keeps working if
catalog/content.py changes later.
"""
import re

from django.db import migrations
from django.utils.text import slugify

NAME_PREFIX_RE = re.compile(r'^[A-Z]{2}(?:\s*\d+(?:\.\d+)*)?:\s*')


def adopt(apps, schema_editor):
    GeneralStep = apps.get_model('catalog', 'GeneralStep')
    Service = apps.get_model('catalog', 'Service')

    used = set()
    for step in GeneralStep.objects.filter(source_key=None).order_by('pk'):
        key = base = slugify(step.title)[:100]
        i = 2
        while key in used or GeneralStep.objects.filter(source_key=key).exists():
            key = f'{base[:95]}-{i}'
            i += 1
        used.add(key)
        step.source_key = key
        step.save(update_fields=['source_key'])

    used = set()
    for service in Service.objects.filter(source_key=None, country__isnull=False).select_related('country').order_by('pk'):
        stem = slugify(NAME_PREFIX_RE.sub('', service.name))[:100] or 'service'
        country = service.country.code.lower()
        key, i = f'{country}/{stem}', 2
        while key in used or Service.objects.filter(source_key=key).exists():
            key = f'{country}/{stem[:95]}-{i}'
            i += 1
        used.add(key)
        service.source_key = key
        service.save(update_fields=['source_key'])


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0005_source_key'),
    ]

    operations = [
        migrations.RunPython(adopt, migrations.RunPython.noop),
    ]
