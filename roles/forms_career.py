import os

from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.models import LearningResource

from .models import Announcement, CareerEvent, MentorshipRequest, Opportunity, Application


class StyledModelForm(forms.ModelForm):
    """Applies the CareerMind input class to every widget."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            if not isinstance(f.widget, (forms.CheckboxInput, forms.ClearableFileInput)):
                f.widget.attrs.setdefault('class', 'input-field')


class OpportunityForm(StyledModelForm):
    class Meta:
        model = Opportunity
        fields = ['title', 'company', 'kind', 'employment_type', 'location', 'pay', 'description',
                  'skills', 'eligibility', 'deadline', 'application_url', 'target_domain', 'target_role']
        widgets = {
            'deadline': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 4}),
            'skills': forms.TextInput(attrs={'placeholder': 'Comma-separated, e.g. Python, SQL, Django'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['target_domain'].required = False
        self.fields['target_role'].required = False
        self.fields['target_domain'].empty_label = 'Any domain'
        self.fields['target_role'].empty_label = 'Any role'
        self.fields['application_url'].label = 'External application link (optional)'

    def clean_title(self):
        v = self.cleaned_data['title'].strip()
        if not v:
            raise forms.ValidationError('Title is required.')
        return v

    def clean_deadline(self):
        d = self.cleaned_data.get('deadline')
        if d and d < timezone.localdate() and (not self.instance.pk or 'deadline' in self.changed_data):
            raise forms.ValidationError('Deadline cannot be in the past.')
        return d

    def clean(self):
        data = super().clean()
        role, domain = data.get('target_role'), data.get('target_domain')
        if role and domain and role.domain_id != domain.pk:
            self.add_error('target_role', 'This role does not belong to the selected domain.')
        return data


ALLOWED_BANNER_EXT = {'.png', '.jpg', '.jpeg', '.webp'}
MAX_BANNER_BYTES = 2 * 1024 * 1024

STAFF_EVENT_TYPES = ['workshop', 'seminar', 'technical', 'guidance', 'placement', 'training']
ALUMNI_EVENT_TYPES = ['industry_talk', 'guidance', 'resume_workshop', 'interview_prep',
                      'technical', 'alumni_interaction', 'industry_experience']


class WorkshopForm(StyledModelForm):
    class Meta:
        model = CareerEvent
        fields = ['title', 'event_type', 'description', 'speaker', 'topic', 'event_date', 'event_time',
                  'location', 'mode', 'meeting_link', 'registration_deadline', 'target_domain', 'banner']
        labels = {'location': 'Venue', 'event_date': 'Date', 'event_time': 'Time',
                  'registration_deadline': 'Registration deadline', 'target_domain': 'Target audience / domain'}
        widgets = {
            'event_date': forms.DateInput(attrs={'type': 'date'}),
            'event_time': forms.TimeInput(attrs={'type': 'time'}),
            'registration_deadline': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, allowed_types=None, **kwargs):
        super().__init__(*args, **kwargs)
        if allowed_types:
            self.fields['event_type'].choices = [c for c in CareerEvent.TYPE_CHOICES if c[0] in allowed_types]
        self.fields['target_domain'].required = False
        self.fields['target_domain'].empty_label = 'All students'
        self.fields['event_time'].required = True
        self.fields['mode'].label = 'Online / Offline'

    def clean_banner(self):
        f = self.cleaned_data.get('banner')
        if f and hasattr(f, 'size'):
            if os.path.splitext(f.name)[1].lower() not in ALLOWED_BANNER_EXT:
                raise forms.ValidationError('Banner must be a PNG, JPG or WEBP image.')
            if f.size > MAX_BANNER_BYTES:
                raise forms.ValidationError('Banner must be 2 MB or smaller.')
        return f

    def clean(self):
        data = super().clean()
        d, rd = data.get('event_date'), data.get('registration_deadline')
        if d and (not self.instance.pk or 'event_date' in self.changed_data) and d < timezone.localdate():
            self.add_error('event_date', 'The date cannot be in the past.')
        if d and rd and rd > d:
            self.add_error('registration_deadline', 'Registration must close on or before the event date.')
        if data.get('mode') == 'online' and not data.get('meeting_link'):
            self.add_error('meeting_link', 'A meeting link is required for online sessions.')
        return data


class ApplicationForm(StyledModelForm):
    class Meta:
        model = Application
        fields = ['cover_note']
        labels = {'cover_note': _('Why are you a good fit? (cover note)')}
        widgets = {'cover_note': forms.Textarea(attrs={'rows': 6, 'maxlength': 2000})}

    def clean_cover_note(self):
        v = (self.cleaned_data.get('cover_note') or '').strip()
        if not v:
            raise forms.ValidationError(_('Please add a short cover note.'))
        return v[:2000]


class MentorshipRequestForm(StyledModelForm):
    class Meta:
        model = MentorshipRequest
        fields = ['topic', 'message']
        labels = {'topic': _('Reason for requesting mentorship'), 'message': _('Short message')}
        widgets = {'message': forms.Textarea(attrs={'rows': 4, 'maxlength': 1000})}

    def clean_topic(self):
        v = (self.cleaned_data['topic'] or '').strip()
        if not v:
            raise forms.ValidationError(_('Please give a reason.'))
        return v

    def clean_message(self):
        v = (self.cleaned_data.get('message') or '').strip()
        if not v:
            raise forms.ValidationError(_('Please add a short message.'))
        return v[:1000]


class AnnouncementForm(StyledModelForm):
    class Meta:
        model = Announcement
        fields = ['title', 'message', 'audience']
        widgets = {'message': forms.Textarea(attrs={'rows': 3, 'maxlength': 280})}

    def clean_message(self):
        return self.cleaned_data['message'].strip()[:280]


class LearningResourceForm(StyledModelForm):
    class Meta:
        model = LearningResource
        fields = ['skill', 'title', 'description', 'youtube_url', 'level', 'duration', 'order', 'resource_type']
        widgets = {'description': forms.Textarea(attrs={'rows': 2})}
