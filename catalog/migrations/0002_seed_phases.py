from django.db import migrations


def seed_phases(apps, schema_editor):
    Phase = apps.get_model('catalog', 'Phase')
    Phase.objects.bulk_create([
        Phase(name='Planning',    slug='planning',    order=1),
        Phase(name='Realisation', slug='realisation', order=2),
        Phase(name='Operation',   slug='operation',   order=3),
    ])


def reverse_seed(apps, schema_editor):
    Phase = apps.get_model('catalog', 'Phase')
    Phase.objects.filter(slug__in=['planning', 'realisation', 'operation']).delete()


class Migration(migrations.Migration):
    dependencies = [('catalog', '0001_initial')]
    operations = [migrations.RunPython(seed_phases, reverse_seed)]
