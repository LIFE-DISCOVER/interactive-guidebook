from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Project, ProjectPhaseEntry


@receiver(post_save, sender=Project)
def create_phase_entry_on_change(sender, instance, created, **kwargs):
    if created:
        ProjectPhaseEntry.objects.create(
            project=instance,
            phase=instance.current_phase,
        )
        return

    # For updates, only create an entry when current_phase was explicitly saved.
    # Callers must use: project.save(update_fields=['current_phase', 'updated_at'])
    update_fields = kwargs.get('update_fields')
    if update_fields and 'current_phase' in update_fields:
        ProjectPhaseEntry.objects.create(
            project=instance,
            phase=instance.current_phase,
        )
