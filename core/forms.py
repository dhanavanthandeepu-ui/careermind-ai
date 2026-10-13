from django import forms
from django.conf import settings
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


def validate_institution_email(email):
    domain = settings.INSTITUTION_EMAIL_DOMAIN
    if not email.lower().endswith('@' + domain.lower()):
        raise forms.ValidationError(
            f"Please use your institution email (must end with @{domain})."
        )


class SignUpForm(UserCreationForm):
    first_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(
        attrs={'placeholder': 'John', 'class': 'input-field'}))
    last_name = forms.CharField(max_length=30, required=True, widget=forms.TextInput(
        attrs={'placeholder': 'Doe', 'class': 'input-field'}))
    email = forms.EmailField(required=True, widget=forms.EmailInput(
        attrs={'placeholder': 'john.doe@university.edu', 'class': 'input-field'}))
    register_number = forms.CharField(max_length=50, required=True, widget=forms.TextInput(
        attrs={'placeholder': 'Student ID / Register Number', 'class': 'input-field'}))
    department = forms.CharField(max_length=120, required=True, widget=forms.TextInput(
        attrs={'placeholder': 'e.g. Computer Science', 'class': 'input-field'}))
    year = forms.CharField(max_length=20, required=True, widget=forms.TextInput(
        attrs={'placeholder': 'e.g. 3rd Year', 'class': 'input-field'}))
    target_role = forms.CharField(max_length=100, required=False, widget=forms.TextInput(
        attrs={'placeholder': 'e.g. Cloud Solutions Architect', 'class': 'input-field'}))

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({'placeholder': '••••••••', 'class': 'input-field'})
        self.fields['password2'].widget.attrs.update({'placeholder': '••••••••', 'class': 'input-field'})
        for name in ('password1', 'password2'):
            self.fields[name].help_text = None

    def clean_email(self):
        email = self.cleaned_data['email']
        validate_institution_email(email)
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.username = self.cleaned_data['email']
        if commit:
            user.save()
        return user
