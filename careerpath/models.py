"""
Career-goal / placement-roadmap data model.

This app extends the existing CareerMind database — it does not touch
or duplicate `core.Profile`, `core.Resume`, `core.Skill` (the student's
personal skill-tracking rows) or `core.LearningResource`. Those keep
working exactly as before.

What lives here is the piece that was previously a hardcoded Python
dict (`ROLE_SKILL_REQUIREMENTS` in core/skill_matching.py): which
skills a given (company, role) pair looks for, plus the student's
career-goal selection and the roadmap generated from it.

Naming note: `Skill` here is a small canonical catalog (just a name),
completely separate from `core.Skill` (a per-student row with
current/target/status). Django keeps them apart automatically via
app label (`careerpath.Skill` vs `core.Skill`); they are never
imported under the same name in the same file.
"""
from django.conf import settings
from django.db import models

from core.models import Profile

PRIORITY_CHOICES = [
    ('critical', 'Critical'),
    ('high', 'High'),
    ('medium', 'Medium'),
    ('low', 'Low'),
]

TIMELINE_CHOICES = [
    (3, '3 Months'),
    (6, '6 Months'),
    (9, '9 Months'),
    (12, '12 Months'),
]


class Company(models.Model):
    name = models.CharField(max_length=120, unique=True)
    is_active = models.BooleanField(
        default=True,
        help_text="Uncleared companies stay in the database but are hidden "
                  "from the student-facing goal picker (soft delete / disable).",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Companies'

    def __str__(self):
        return self.name


class CareerDomain(models.Model):
    """A broad career track, e.g. 'Data Analytics', 'Web Development'.
    One domain groups several CareerRoles."""
    name = models.CharField(max_length=120, unique=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class CareerRole(models.Model):
    """A job role, e.g. 'Data Analyst'. Belongs to one domain, but the
    same role name can be required by many different companies via
    RoleSkillRequirement."""
    domain = models.ForeignKey(CareerDomain, on_delete=models.PROTECT, related_name='roles')
    name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['domain__name', 'name']
        unique_together = ('domain', 'name')

    def __str__(self):
        return f"{self.name} ({self.domain.name})"


class Skill(models.Model):
    """Canonical skill catalog entry (just a name). Values here should
    match the canonical forms core/resume_parser.py normalizes extracted
    resume skills to, since skill-gap matching is a plain case-insensitive
    name comparison — no fuzzy/AI matching involved."""
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class RoleSkillRequirement(models.Model):
    """
    'Company X, Role Y requires Skill Z, at Priority P.' The
    database-driven replacement for the old hardcoded
    ROLE_SKILL_REQUIREMENTS dict.

    `source` and `last_updated` exist so nothing here is presented as a
    silently-verified fact: seed data is clearly labelled as a generic,
    editable starting point (see seed_companies command), and an Admin
    can update the source/priority per row as real requirements are
    confirmed.
    """
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='requirements')
    role = models.ForeignKey(CareerRole, on_delete=models.CASCADE, related_name='requirements')
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name='requirements')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    source = models.CharField(
        max_length=255,
        default='Generic industry baseline (not company-verified) — update via Admin.',
    )
    last_updated = models.DateField(auto_now=True)

    class Meta:
        ordering = ['company__name', 'role__name', 'priority']
        unique_together = ('company', 'role', 'skill')

    def __str__(self):
        return f"{self.company} / {self.role.name} needs {self.skill}"


class StudentCareerGoal(models.Model):
    """The student's current career-goal selection. One row per student
    (setting a new goal updates this row in place, which also drives
    regenerating the roadmap below)."""
    profile = models.OneToOneField(Profile, on_delete=models.CASCADE, related_name='career_goal')
    domain = models.ForeignKey(CareerDomain, on_delete=models.PROTECT, related_name='+')
    role = models.ForeignKey(CareerRole, on_delete=models.PROTECT, related_name='+')
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name='+')
    timeline_months = models.PositiveIntegerField(choices=TIMELINE_CHOICES, default=6)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.profile.user.username} → {self.role.name} @ {self.company.name}"


class Roadmap(models.Model):
    goal = models.OneToOneField(StudentCareerGoal, on_delete=models.CASCADE, related_name='roadmap')
    generated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Roadmap<{self.goal}>"

    @property
    def progress_percentage(self):
        total = self.milestones.count()
        if not total:
            return 0
        done = self.milestones.filter(is_completed=True).count()
        return round(100 * done / total)


class RoadmapMilestone(models.Model):
    """One month of the roadmap. `tasks` is a plain list of task strings
    (JSONField) — generated deterministically from real skill gaps, see
    careerpath/services.py; nothing here is free-text-invented."""
    roadmap = models.ForeignKey(Roadmap, on_delete=models.CASCADE, related_name='milestones')
    month_number = models.PositiveIntegerField()
    title = models.CharField(max_length=200)
    tasks = models.JSONField(default=list, blank=True)
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['month_number']
        unique_together = ('roadmap', 'month_number')

    def __str__(self):
        return f"Month {self.month_number}: {self.title}"
