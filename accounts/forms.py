from django import forms
from django.contrib.auth import password_validation
from django.utils.translation import gettext_lazy as _

from catalog.models import Country

from .models import CustomUser
from .setup import check_setup_code


class SetupForm(forms.Form):
    """Creates the first administrator account."""

    setup_code = forms.CharField(
        label=_('Setup code'),
        help_text=_('Shown in the server log. You can also print it with: python manage.py setup_code'),
        widget=forms.TextInput(attrs={'autocomplete': 'off', 'autofocus': True}),
    )
    first_name = forms.CharField(label=_('First name'), max_length=150)
    last_name = forms.CharField(label=_('Last name'), max_length=150)
    email = forms.EmailField(label=_('Administrator email'), help_text=_('You will use this address to sign in.'))
    country = forms.ModelChoiceField(
        queryset=Country.objects.all(),
        required=False,
        label=_('Country'),
        empty_label=_('All countries'),
        help_text=_('Limits the service catalog to this country. Can be changed later.'),
    )
    password1 = forms.CharField(
        label=_('Password'),
        strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        help_text=password_validation.password_validators_help_text_html(),
    )
    password2 = forms.CharField(
        label=_('Confirm password'),
        strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
    )

    def clean_setup_code(self):
        code = self.cleaned_data['setup_code']
        if not check_setup_code(code):
            raise forms.ValidationError(_('This setup code is not correct.'))
        return code

    def clean_email(self):
        return CustomUser.objects.normalize_email(self.cleaned_data['email'])

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get('password1')
        password2 = cleaned.get('password2')
        if password1 and password2 and password1 != password2:
            self.add_error('password2', _('The two passwords do not match.'))
        elif password1:
            user = CustomUser(
                email=cleaned.get('email', ''),
                first_name=cleaned.get('first_name', ''),
                last_name=cleaned.get('last_name', ''),
            )
            try:
                password_validation.validate_password(password1, user)
            except forms.ValidationError as error:
                self.add_error('password1', error)
        return cleaned

    def save(self):
        return CustomUser.objects.create_superuser(
            email=self.cleaned_data['email'],
            password=self.cleaned_data['password1'],
            first_name=self.cleaned_data['first_name'],
            last_name=self.cleaned_data['last_name'],
            country=self.cleaned_data['country'],
        )
