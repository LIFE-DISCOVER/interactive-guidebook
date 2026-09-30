import secrets
from datetime import date

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import translation
from django.utils.translation import gettext_lazy as _

from catalog.models import Phase, Service


class Initiator(models.Model):
    first_name = models.CharField(_('first name'), max_length=100)
    last_name = models.CharField(_('last name'), max_length=100)
    email = models.EmailField(_('email'), unique=True)
    phone = models.CharField(_('phone'), max_length=30, blank=True)
    organization = models.CharField(_('organization'), max_length=200, blank=True)
    notes = models.TextField(_('notes'), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('initiator')
        verbose_name_plural = _('initiators')

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def __str__(self):
        return self.full_name


class Project(models.Model):
    STATUS_CHOICES = [
        ('active', _('Active')),
        ('on_hold', _('On Hold')),
        ('completed', _('Completed')),
        ('cancelled', _('Cancelled')),
    ]
    CATEGORY_CHOICES = [
        ('rec', _('Renewable Energy Community')),
        ('cec', _('Citizen Energy Community')),
        ('csc', _('Collective Self Consumption')),
        ('other', _('Other')),
    ]
    initiator = models.ForeignKey(
        Initiator, on_delete=models.PROTECT, related_name='projects', verbose_name=_('initiator'),
    )
    name = models.CharField(_('name'), max_length=200)
    description = models.TextField(_('description'), blank=True)
    current_phase = models.ForeignKey(
        Phase, on_delete=models.PROTECT, related_name='projects', verbose_name=_('current phase'),
    )
    status = models.CharField(_('status'), max_length=20, choices=STATUS_CHOICES, default='active')
    started_on = models.DateField(_('started on'), null=True, blank=True)
    # Technical & financial details
    category = models.CharField(
        _('category'), max_length=10, choices=CATEGORY_CHOICES, blank=True,
        help_text=_('Legal/organisational category of the community energy project.'),
    )
    power_installed = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text=_('Total installed PV capacity in kWp.'),
        verbose_name=_('Power installed (kWp)'),
    )
    energy_generation = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text=_('Annual energy generation in kWh.'),
        verbose_name=_('Energy generation (kWh/year)'),
    )
    investment = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True,
        help_text=_('Total investment in renewable energy in EUR.'),
        verbose_name=_('Investment in renewable energy (EUR)'),
    )
    address = models.TextField(_('address'), blank=True, help_text=_('Project site address.'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('project')
        verbose_name_plural = _('projects')

    def __str__(self):
        return self.name


class ProjectPhaseEntry(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='phase_entries')
    phase = models.ForeignKey(Phase, on_delete=models.PROTECT)
    entered_on = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-entered_on']

    def __str__(self):
        return f"{self.project} — {self.phase} ({self.entered_on:%Y-%m-%d})"


class ServiceApplication(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='service_applications')
    service = models.ForeignKey(Service, on_delete=models.PROTECT, verbose_name=_('service'))
    applied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('applied by'),
    )
    applied_on = models.DateField(_('applied on'), default=date.today)
    outcome_notes = models.TextField(_('outcome notes'), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['project', 'service'], name='unique_project_service')
        ]

    def __str__(self):
        return f"{self.service} → {self.project}"


def generate_link_token():
    return secrets.token_urlsafe(32)


class ServiceLink(models.Model):
    """Single-use link that lets an initiator read about an applied service and leave a note."""

    application = models.ForeignKey(
        ServiceApplication, on_delete=models.CASCADE, related_name='links', verbose_name=_('applied service'),
    )
    token = models.CharField(max_length=64, unique=True, default=generate_link_token, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_('created by'),
    )
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)
    message = models.TextField(_('personal message'), max_length=2000, blank=True)
    is_active = models.BooleanField(_('active'), default=True)
    note = models.TextField(_('note from initiator'), blank=True)
    submitted_at = models.DateTimeField(_('submitted at'), null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = _('service link')
        verbose_name_plural = _('service links')

    def __str__(self):
        return f"{self.application} ({self.created_at:%Y-%m-%d})"

    @property
    def is_used(self):
        return self.submitted_at is not None

    def get_public_path(self):
        """Path without language prefix, so the initiator gets their browser language."""
        with translation.override(settings.LANGUAGE_CODE):
            path = reverse('service_link', args=[self.token])
        return path.removeprefix(f'/{settings.LANGUAGE_CODE}')
