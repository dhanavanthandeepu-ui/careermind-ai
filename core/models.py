from django.contrib.auth.models import User
from django.db import models


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    university_email = models.EmailField(blank=True)
    role = models.CharField(max_length=20, default='student')
    # Only meaningful for role='staff' (Faculty): a Faculty account cannot
    # log in until an Admin approves it. Defaults to True so it never
    # affects Student/Alumni/Admin accounts.
    is_approved = models.BooleanField(default=True)
    target_role = models.CharField(max_length=100, default='Cloud Solutions Architect')
    readiness_score = models.PositiveIntegerField(default=0)
    readiness_delta = models.CharField(max_length=20, blank=True, default='')
    resume_score = models.PositiveIntegerField(default=0)
    skills_acquired = models.PositiveIntegerField(default=0)
    interview_rate = models.PositiveIntegerField(default=0)
    critical_gaps = models.PositiveIntegerField(default=0)
    certified_skills = models.PositiveIntegerField(default=0)
    next_milestone = models.CharField(max_length=100, blank=True, default='')
    weeks_to_milestone = models.PositiveIntegerField(default=0)

    # NOTE: readiness_score / resume_score / skills_acquired / critical_gaps /
    # certified_skills are *derived* values. They are written only by
    # core.metrics.sync_profile_metrics() from the student's real resume
    # analysis so staff/admin/alumni screens that read them show real data.
    # interview_rate, readiness_delta, next_milestone and weeks_to_milestone
    # are legacy columns with no real data source and are not displayed.

    def __str__(self):
        return f"Profile<{self.user.username}>"


class Skill(models.Model):
    CATEGORY_CHOICES = [
        ('technical', 'Technical'),
        ('soft', 'Soft'),
        ('leadership', 'Leadership'),
    ]
    STATUS_CHOICES = [
        ('growing', 'Growing'),
        ('stable', 'Stable'),
    ]
    PRIORITY_CHOICES = [
        ('high', 'High Priority'),
        ('medium', 'Medium Priority'),
        ('low', 'Low Priority'),
    ]

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='skills')
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='technical')
    current = models.PositiveIntegerField(default=50)
    target = models.PositiveIntegerField(default=80)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='stable')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')

    class Meta:
        ordering = ['-priority', 'name']

    def __str__(self):
        return f"{self.name} ({self.current}/{self.target})"


DEFAULT_SKILLS = [
    dict(name="Machine Learning", category="technical", current=65, target=90, status="growing", priority="high"),
    dict(name="Cloud Architecture", category="technical", current=40, target=85, status="stable", priority="high"),
    dict(name="Python Mastery", category="technical", current=85, target=95, status="growing", priority="medium"),
    dict(name="Strategic Leadership", category="leadership", current=30, target=70, status="stable", priority="medium"),
    dict(name="Data Visualization", category="technical", current=75, target=80, status="growing", priority="low"),
    dict(name="Communication", category="soft", current=80, target=90, status="growing", priority="high"),
    dict(name="Agile Methodologies", category="soft", current=50, target=85, status="stable", priority="medium"),
]


class Resume(models.Model):
    """An uploaded resume PDF plus the information extracted from it."""
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='resumes')
    file = models.FileField(upload_to='resumes/%Y/%m/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    raw_text = models.TextField(blank=True)

    skills = models.JSONField(default=list, blank=True)
    education = models.JSONField(default=list, blank=True)
    projects = models.JSONField(default=list, blank=True)
    certifications = models.JSONField(default=list, blank=True)
    experience = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"Resume<{self.profile.user.username}, {self.uploaded_at:%Y-%m-%d}>"


class LearningResource(models.Model):
    """
    A single curated learning resource (video/playlist/course/etc.) for
    one skill. `skill` should match the canonical skill names used by
    resume_parser.py / skill_matching.py (e.g. "Power BI", "SQL"), since
    the Learning Path looks resources up by exact skill name.

    youtube_url values must be real, manually-verified links — never
    generated/guessed video IDs.
    """
    RESOURCE_TYPE_CHOICES = [
        ('video', 'Video'), ('playlist', 'Playlist'), ('course', 'Course'),
        ('practice', 'Practice'), ('project', 'Project'),
    ]
    LEVEL_CHOICES = [('beginner', 'Beginner'), ('intermediate', 'Intermediate'), ('advanced', 'Advanced')]

    skill = models.CharField(max_length=100, db_index=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    youtube_url = models.URLField()
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='beginner')
    duration = models.CharField(max_length=50, blank=True, default='')
    order = models.PositiveIntegerField(default=1)
    resource_type = models.CharField(max_length=20, choices=RESOURCE_TYPE_CHOICES, default='video')
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['skill', 'order']

    def __str__(self):
        return f"{self.skill}: {self.title}"


class StudentLearningProgress(models.Model):
    STATUS_CHOICES = [
        ('not_started', 'Not Started'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    ]

    student = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='learning_progress')
    resource = models.ForeignKey(LearningResource, on_delete=models.CASCADE, related_name='student_progress')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='not_started')
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('student', 'resource')

    def __str__(self):
        return f"{self.student.user.username} / {self.resource.title} / {self.status}"
