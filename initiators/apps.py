from django.apps import AppConfig


class InitiatorsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'initiators'

    def ready(self):
        import initiators.signals  # noqa: F401
