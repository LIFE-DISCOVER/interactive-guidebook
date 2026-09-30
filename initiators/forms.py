from django import forms
from django.utils.translation import gettext_lazy as _

from catalog.models import Phase, Service
from .models import Initiator, Project, ServiceApplication, ServiceLink


class InitiatorForm(forms.ModelForm):
    class Meta:
        model = Initiator
        fields = ['first_name', 'last_name', 'email', 'phone', 'organization', 'notes']


_PROJECT_EXTRA_FIELDS = [
    'category', 'address', 'power_installed', 'energy_generation', 'investment',
]
_PROJECT_WIDGETS = {
    'started_on': forms.DateInput(attrs={'type': 'date'}),
    'description': forms.Textarea(attrs={'rows': 3}),
    'address': forms.Textarea(attrs={'rows': 2}),
}


class ProjectCreateForm(forms.ModelForm):
    """Used on project creation — includes current_phase for initial assignment."""
    class Meta:
        model = Project
        fields = ['name', 'description', 'current_phase', 'status', 'started_on'] + _PROJECT_EXTRA_FIELDS
        widgets = _PROJECT_WIDGETS


class ProjectForm(forms.ModelForm):
    """General project edit — current_phase is changed via the dedicated phase-change view."""
    class Meta:
        model = Project
        fields = ['name', 'description', 'status', 'started_on'] + _PROJECT_EXTRA_FIELDS
        widgets = _PROJECT_WIDGETS


class ProjectPhaseChangeForm(forms.Form):
    """Dedicated form for changing the project phase plus an optional note."""
    current_phase = forms.ModelChoiceField(
        queryset=Phase.objects.all(),
        label=_('New Phase'),
    )
    notes = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False,
        label=_('Notes (optional)'),
        help_text=_('Reason for the phase change or any relevant context.'),
    )


class ServiceApplicationForm(forms.ModelForm):
    class Meta:
        model = ServiceApplication
        fields = ['service', 'applied_on', 'outcome_notes']
        widgets = {
            'applied_on': forms.DateInput(attrs={'type': 'date'}),
            'outcome_notes': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, project=None, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.project = project
        services = Service.objects.filter(is_active=True).order_by('name')
        # Same scoping as the service catalog: managers only see their own country.
        if user is not None and getattr(user, 'country_id', None):
            services = services.filter(country_id=user.country_id)
        self.fields['service'].queryset = services

    def clean_service(self):
        # project is set by the view, so the model's unique (project, service)
        # constraint is not checked by ModelForm validation; check it here.
        service = self.cleaned_data['service']
        if self.project and self.project.service_applications.filter(service=service).exists():
            raise forms.ValidationError(_('This service has already been applied to this project.'))
        return service


class ServiceLinkCreateForm(forms.ModelForm):
    """Manager: optional personal message sent along with a new link."""

    class Meta:
        model = ServiceLink
        fields = ['message']
        labels = {'message': _('Personal message for the initiator (optional)')}
        help_texts = {'message': _('Shown at the top of the page the initiator opens.')}
        widgets = {'message': forms.Textarea(attrs={'rows': 3, 'maxlength': 2000})}


class ServiceLinkNoteForm(forms.Form):
    """Initiator: the note they send back through the link."""

    note = forms.CharField(
        label=_('Your note'),
        max_length=5000,
        widget=forms.Textarea(attrs={'rows': 6, 'maxlength': 5000}),
        help_text=_('You can send this note once.'),
    )
