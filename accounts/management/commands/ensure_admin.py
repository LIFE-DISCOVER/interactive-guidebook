import os

from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand
from django.core.validators import validate_email


class Command(BaseCommand):
    help = (
        'On first launch, create the administrator from DJANGO_SUPERUSER_EMAIL and '
        'DJANGO_SUPERUSER_PASSWORD so the setup page is skipped. Does nothing once '
        'any user exists.'
    )

    def handle(self, *args, **options):
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL', '').strip()
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', '')
        if not email and not password:
            return
        if not email or not password:
            self.stderr.write(
                'Administrator not created: set both DJANGO_SUPERUSER_EMAIL and '
                'DJANGO_SUPERUSER_PASSWORD. The setup page remains available.'
            )
            return

        User = get_user_model()
        if User.objects.exists():
            self.stdout.write(
                'Users already exist; DJANGO_SUPERUSER_EMAIL/PASSWORD are ignored '
                'and can be removed from .env.'
            )
            return

        email = User.objects.normalize_email(email)
        try:
            validate_email(email)
            password_validation.validate_password(password, User(email=email))
        except ValidationError as error:
            self.stderr.write(
                'Administrator not created: ' + ' '.join(error.messages) +
                ' Fix .env and restart, or use the setup page.'
            )
            return

        User.objects.create_superuser(email=email, password=password)
        self.stdout.write(f'Created administrator {email}; first-run setup skipped.')
