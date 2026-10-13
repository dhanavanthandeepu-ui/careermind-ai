from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext, gettext_lazy as _

from core.models import Profile


# ---------------------------------------------------------------- profiles
class StudentDetail(models.Model):
    profile = models.OneToOneField(Profile, on_delete=models.CASCADE, related_name='student_detail')
    register_number = models.CharField(max_length=50, blank=True, default='')
    department = models.CharField(max_length=120, blank=True, default='')
    year = models.CharField(max_length=20, blank=True, default='')

    def __str__(self):
        return f"StudentDetail<{self.profile.user.username}>"


class StaffDetail(models.Model):
    profile = models.OneToOneField(Profile, on_delete=models.CASCADE, related_name='staff_detail')
    employee_id = models.CharField(max_length=50, blank=True, default='')
    department = models.CharField(max_length=120, default='Placement Cell')
    designation = models.CharField(max_length=120, default='Career Counselor')
    students_assigned = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"StaffDetail<{self.profile.user.username}>"


class AlumniDetail(models.Model):
    profile = models.OneToOneField(Profile, on_delete=models.CASCADE, related_name='alumni_detail')
    current_company = models.CharField(max_length=120, default='—')
    designation = models.CharField(max_length=120, default='—')
    graduation_year = models.PositiveIntegerField(default=2022)
    experience_years = models.PositiveIntegerField(default=1)
    industry = models.CharField(max_length=120, default='Technology')
    bio = models.TextField(blank=True, default='')
    willing_to_mentor = models.BooleanField(default=True)

    def __str__(self):
        return f"AlumniDetail<{self.profile.user.username}>"


class AdminDetail(models.Model):
    profile = models.OneToOneField(Profile, on_delete=models.CASCADE, related_name='admin_detail')
    designation = models.CharField(max_length=120, default='Platform Administrator')

    def __str__(self):
        return f"AdminDetail<{self.profile.user.username}>"


# ---------------------------------------------------------------- shared platform data
class Opportunity(models.Model):
    KIND_CHOICES = [('job', _('Job')), ('internship', _('Internship'))]
    # 'open' == Published (kept as the stored value so existing rows/queries
    # keep working). Approval flow: pending -> open (approved) | rejected.
    STATUS_CHOICES = [
        ('draft', _('Draft')),
        ('pending', _('Pending Approval')), ('open', _('Published')),
        ('rejected', _('Rejected')), ('closed', _('Closed')),
    ]
    EMPLOYMENT_CHOICES = [
        ('full_time', _('Full-time')), ('part_time', _('Part-time')),
        ('contract', _('Contract')), ('internship', _('Internship')), ('other', _('Other')),
    ]

    title = models.CharField(max_length=150)
    company = models.CharField(max_length=120)
    kind = models.CharField(max_length=12, choices=KIND_CHOICES, default='job')
    location = models.CharField(max_length=120, default='Remote')
    pay = models.CharField(max_length=80, blank=True, default='')
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='open')
    posted_by_alumni = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='posted_opportunities')
    deadline = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # Added for alumni posting + skill-based recommendations.
    skills = models.CharField(max_length=300, blank=True, default='',
                              help_text="Comma-separated, e.g. Python, SQL, Django")
    eligibility = models.CharField(max_length=200, blank=True, default='')
    description = models.TextField(blank=True, default='')
    application_url = models.URLField(blank=True, default='')
    review_note = models.CharField(max_length=300, blank=True, default='')
    reviewed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='reviewed_opportunities')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    # Career-services additions: employment type + the (existing) career
    # domain / role catalog from careerpath, used to prioritise postings for
    # students whose Career Goal matches.
    employment_type = models.CharField(max_length=12, choices=EMPLOYMENT_CHOICES, default='full_time')
    target_domain = models.ForeignKey('careerpath.CareerDomain', null=True, blank=True,
                                      on_delete=models.SET_NULL, related_name='opportunities')
    target_role = models.ForeignKey('careerpath.CareerRole', null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name='opportunities')

    class Meta:
        ordering = ['-created_at']

    @property
    def skill_list(self):
        return [x.strip() for x in self.skills.split(',') if x.strip()]

    @property
    def is_published(self):
        return self.status == 'open'

    @property
    def is_expired(self):
        return bool(self.deadline and self.deadline < timezone.localdate())

    @property
    def posted_by_name(self):
        u = self.posted_by_alumni
        if u:
            return u.get_full_name() or u.username
        return 'Placement Cell'

    def __str__(self):
        return f"{self.title} @ {self.company}"


class CareerEvent(models.Model):
    """Workshops, seminars, sessions and career events (one table for all of
    them). Rows created before the approval workflow existed default to
    'published', so nothing already visible disappears."""
    TYPE_CHOICES = [
        ('event', _('Career Event')),
        ('workshop', _('Workshop')),
        ('seminar', _('Seminar')),
        ('technical', _('Technical Session')),
        ('guidance', _('Career Guidance Session')),
        ('placement', _('Placement Session')),
        ('training', _('Training Program')),
        ('industry_talk', _('Industry Talk')),
        ('resume_workshop', _('Resume Workshop')),
        ('interview_prep', _('Interview Preparation Session')),
        ('alumni_interaction', _('Alumni Interaction Session')),
        ('industry_experience', _('Industry Experience Session')),
    ]
    MODE_CHOICES = [('offline', _('Offline')), ('online', _('Online'))]
    STATUS_CHOICES = [
        ('draft', _('Draft')), ('pending', _('Pending Approval')), ('published', _('Published')),
        ('rejected', _('Rejected')), ('cancelled', _('Cancelled')),
    ]

    title = models.CharField(max_length=150)
    description = models.TextField(blank=True, default='')
    event_date = models.DateField()
    location = models.CharField(max_length=120, default='Campus Auditorium', help_text='Venue')
    organizer = models.CharField(max_length=120, default='Placement Cell')
    event_type = models.CharField(max_length=24, choices=TYPE_CHOICES, default='event')
    speaker = models.CharField(max_length=120, blank=True, default='')
    topic = models.CharField(max_length=120, blank=True, default='')
    event_time = models.TimeField(null=True, blank=True)
    mode = models.CharField(max_length=8, choices=MODE_CHOICES, default='offline')
    meeting_link = models.URLField(blank=True, default='')
    registration_deadline = models.DateField(null=True, blank=True)
    target_domain = models.ForeignKey('careerpath.CareerDomain', null=True, blank=True,
                                      on_delete=models.SET_NULL, related_name='events')
    banner = models.FileField(upload_to='event_banners/%Y/%m/', blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='published')
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='created_events')
    review_note = models.CharField(max_length=300, blank=True, default='')
    reviewed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='reviewed_events')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        ordering = ['event_date']

    def __str__(self):
        return self.title

    @property
    def is_published(self):
        return self.status == 'published'

    @property
    def is_online(self):
        return self.mode == 'online'

    @property
    def is_past(self):
        return self.event_date < timezone.localdate()

    @property
    def registration_open(self):
        """Published, not finished, and the registration deadline (if any) has not passed."""
        today = timezone.localdate()
        if self.status != 'published' or self.event_date < today:
            return False
        return not (self.registration_deadline and self.registration_deadline < today)

    @property
    def posted_by_name(self):
        u = self.created_by
        if u:
            return u.get_full_name() or u.username
        return self.organizer

    @property
    def notification_type(self):
        return 'seminar' if self.event_type == 'seminar' else 'workshop'

    def get_student_url(self):
        return reverse('student:workshop_detail', args=[self.pk])


class Course(models.Model):
    title = models.CharField(max_length=150)
    provider = models.CharField(max_length=120, default='CareerMind Learning')
    category = models.CharField(max_length=80, default='Technical')
    duration_weeks = models.PositiveIntegerField(default=4)
    enrolled_count = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.title


class MentorshipRequest(models.Model):
    # Stored value 'declined' is kept for existing rows; it is shown as "Rejected".
    STATUS_CHOICES = [('pending', _('Pending')), ('accepted', _('Accepted')), ('declined', _('Rejected')), ('completed', _('Completed'))]
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mentorship_requests_made')
    alumni = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='mentorship_requests_received')
    # `topic` holds the student's short reason for requesting mentorship.
    topic = models.CharField(max_length=150, default='Career Guidance')
    message = models.TextField(blank=True, default='')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            # At most one pending request per (student, alumni) pair.
            models.UniqueConstraint(fields=['student', 'alumni'], condition=models.Q(status='pending'),
                                    name='uniq_pending_mentorship_per_pair'),
        ]


class GuidanceRequest(models.Model):
    STATUS_CHOICES = [('open', _('Open')), ('in_progress', _('In Progress')), ('resolved', _('Resolved'))]
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='guidance_requests')
    staff = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='guidance_assigned')
    topic = models.CharField(max_length=150, default='Career Guidance')
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='open')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class ResumeReview(models.Model):
    STATUS_CHOICES = [
        ('pending', _('Pending Review')), ('reviewed', _('Reviewed')),
        ('changes_requested', _('Improvement Requested')),
    ]
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='resume_reviews')
    # The specific resume the student submitted for review (null for rows
    # created before this field existed).
    resume = models.ForeignKey('core.Resume', null=True, blank=True, on_delete=models.SET_NULL, related_name='reviews')
    reviewer = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='reviews_done')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True, default='')
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-submitted_at']


class StudentActivity(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activities')
    description = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Student activities'


class Notification(models.Model):
    TYPE_CHOICES = [
        ('workshop', _('Workshop')), ('seminar', _('Seminar')), ('job', _('Job')),
        ('internship', _('Internship')), ('mentorship', _('Mentorship')),
        ('application', _('Application status')), ('announcement', _('Announcement')),
        ('learning_resource', _('Learning resource')), ('career_update', _('Career update')),
        ('general', _('General')),
    ]
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=150, blank=True, default='')
    message = models.CharField(max_length=300)
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='general')
    # Optional related object (Opportunity, CareerEvent, MentorshipRequest, ...)
    content_type = models.ForeignKey(ContentType, null=True, blank=True, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    related_object = GenericForeignKey('content_type', 'object_id')
    link = models.CharField(max_length=255, blank=True, default='', help_text='Internal path opened when the notification is clicked')
    # msgid + params so the text can be shown in the *reader's* language
    message_key = models.CharField(max_length=300, blank=True, default='')
    message_params = models.JSONField(default=dict, blank=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['recipient', 'is_read'], name='notif_recipient_read_idx')]

    def __str__(self):
        return f"{self.recipient_id}: {self.title or self.message[:40]}"

    @property
    def display_title(self):
        return gettext(self.title) if self.title else ''

    @property
    def display_message(self):
        if self.message_key:
            try:
                return gettext(self.message_key) % self.message_params
            except (KeyError, TypeError, ValueError):
                pass
        return self.message


class Message(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class Referral(models.Model):
    STATUS_CHOICES = [('submitted', _('Submitted')), ('in_review', _('In Review')), ('hired', _('Hired')), ('rejected', _('Rejected'))]
    alumni = models.ForeignKey(User, on_delete=models.CASCADE, related_name='referrals_made')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='referrals_received')
    opportunity = models.ForeignKey(Opportunity, null=True, blank=True, on_delete=models.SET_NULL, related_name='referrals')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='submitted')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


# ---------------------------------------------------------------- career services (new)
class Application(models.Model):
    """A student's application to a published Opportunity (job or internship)."""
    STATUS_CHOICES = [
        ('applied', _('Applied')), ('under_review', _('Under Review')),
        ('shortlisted', _('Shortlisted')), ('rejected', _('Rejected')), ('selected', _('Selected')),
    ]
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='applications')
    opportunity = models.ForeignKey(Opportunity, on_delete=models.CASCADE, related_name='applications')
    resume = models.ForeignKey('core.Resume', null=True, blank=True, on_delete=models.SET_NULL, related_name='applications')
    cover_note = models.TextField(blank=True, default='')
    status = models.CharField(max_length=14, choices=STATUS_CHOICES, default='applied')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['student', 'opportunity'], name='uniq_application_per_student_opportunity'),
        ]

    def __str__(self):
        return f"{self.student_id} -> {self.opportunity_id} ({self.status})"


class EventRegistration(models.Model):
    event = models.ForeignKey(CareerEvent, on_delete=models.CASCADE, related_name='registrations')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='event_registrations')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['event', 'student'], name='uniq_registration_per_student_event'),
        ]


class Announcement(models.Model):
    AUDIENCE_CHOICES = [
        ('all', 'Everyone'), ('student', 'Students'), ('staff', 'Staff'), ('alumni', 'Alumni'),
    ]
    title = models.CharField(max_length=150)
    message = models.TextField()
    audience = models.CharField(max_length=10, choices=AUDIENCE_CHOICES, default='student')
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='announcements')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title
