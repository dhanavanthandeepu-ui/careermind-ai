from django import forms

from .models import CareerDomain, CareerRole, Company, StudentCareerGoal, TIMELINE_CHOICES


class CareerGoalForm(forms.ModelForm):
    domain = forms.ModelChoiceField(
        queryset=CareerDomain.objects.all(),
        widget=forms.Select(attrs={'class': 'input-field'}),
    )
    role = forms.ModelChoiceField(
        queryset=CareerRole.objects.filter(is_active=True).select_related('domain'),
        widget=forms.Select(attrs={'class': 'input-field'}),
    )
    company = forms.ModelChoiceField(
        queryset=Company.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'input-field'}),
    )
    timeline_months = forms.TypedChoiceField(
        choices=TIMELINE_CHOICES, coerce=int,
        widget=forms.Select(attrs={'class': 'input-field'}),
    )

    class Meta:
        model = StudentCareerGoal
        fields = ['domain', 'role', 'company', 'timeline_months']

    def clean(self):
        cleaned = super().clean()
        domain = cleaned.get('domain')
        role = cleaned.get('role')
        if domain and role and role.domain_id != domain.id:
            self.add_error('role', "This role doesn't belong to the selected domain.")
        return cleaned
