from django.core.management.base import BaseCommand, CommandError

from catalog.content import CONTENT_DIR, ContentError, load_content, sync_content


class Command(BaseCommand):
    help = 'Make countries, guidebook steps and services match the YAML files in data/.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Only report what would change.')
        parser.add_argument('--path', default=str(CONTENT_DIR), help='Content directory (default: data/).')
        parser.add_argument('--list-changes', action='store_true', help='List every changed item.')

    def handle(self, *args, **options):
        try:
            content = load_content(options['path'])
        except ContentError as exc:
            raise CommandError(str(exc))
        report = sync_content(content, dry_run=options['dry_run'])
        prefix = 'Dry run — would change' if options['dry_run'] else 'Content synced'
        self.stdout.write(f'{prefix}:')
        for line in report.summary():
            self.stdout.write(f'  {line}')
        if options['list_changes'] or options['dry_run']:
            for change in report.changes:
                self.stdout.write(f'  - {change}')
        for warning in report.warnings:
            self.stdout.write(self.style.WARNING(f'  Warning: {warning}'))
