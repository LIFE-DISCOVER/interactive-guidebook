from django.core.management.base import BaseCommand

from accounts.setup import setup_code, setup_required


class Command(BaseCommand):
    help = 'Print the code needed on the first-run setup page.'

    def handle(self, *args, **options):
        if not setup_required():
            self.stdout.write('Setup is already complete: at least one user exists.')
            return
        self.stdout.write(f'Setup code: {setup_code()}')
