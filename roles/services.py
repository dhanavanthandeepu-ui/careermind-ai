"""Shared helpers: relevance of content to students, ranking of opportunities."""
from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone

from core.models import Profile


def student_domain_ids(profile):
    """Career domains relevant to a student: the domain of their saved Career
    Goal, plus the domain(s) of any catalog role matching their target role."""
    from careerpath.models import CareerRole, StudentCareerGoal
    ids = set()
    goal = StudentCareerGoal.objects.filter(profile=profile).first()
    if goal:
        ids.add(goal.domain_id)
    if profile.target_role:
        ids.update(CareerRole.objects.filter(name__iexact=profile.target_role).values_list('domain_id', flat=True))
    return ids


def students_for_domain(domain=None, role=None):
    """Active students who should hear about content targeted at `domain`
    (and optionally `role`). With no target, every active student."""
    base = User.objects.filter(is_active=True, profile__role='student')
    if domain is None and role is None:
        return list(base)
    out = []
    for u in base.select_related('profile'):
        goal = _goal(u.profile)
        if domain is not None and domain.pk in student_domain_ids(u.profile):
            out.append(u)
        elif role is not None and goal and goal.role_id == role.pk:
            out.append(u)
    return out


def _goal(profile):
    from careerpath.models import StudentCareerGoal
    return StudentCareerGoal.objects.filter(profile=profile).select_related('role', 'domain').first()


def visible_events_for(profile, upcoming_only=True):
    """Published events a student should see: untargeted or matching their domain."""
    from .models import CareerEvent
    qs = CareerEvent.objects.filter(status='published').select_related('target_domain', 'created_by')
    if upcoming_only:
        qs = qs.filter(event_date__gte=timezone.localdate())
    return qs.filter(Q(target_domain__isnull=True) | Q(target_domain_id__in=student_domain_ids(profile)))


def published_opportunities(kind=None):
    from .models import Opportunity
    today = timezone.localdate()
    qs = Opportunity.objects.filter(status='open').filter(Q(deadline__isnull=True) | Q(deadline__gte=today))
    if kind:
        qs = qs.filter(kind=kind)
    return qs.select_related('posted_by_alumni', 'target_domain', 'target_role')


def rank_opportunities(profile, opps):
    """Annotate and order opportunities for a student using real data only.

    - o.match: % of the posting's listed skills found in the student's resume
      (same calculation the dashboard already used); None when the posting lists
      no skills or the student has no analysed resume. Never invented.
    - o.for_goal: True when the posting targets the student's Career Goal
      role/domain (or their target role).
    - o.skills_have / o.skills_missing: real overlap lists.
    """
    resume = profile.resumes.first()
    have = {s.lower() for s in (resume.skills if resume else [])}
    goal = _goal(profile)
    domains = student_domain_ids(profile)
    target_role = (profile.target_role or '').strip().lower()
    out = []
    for o in opps:
        wanted = o.skill_list
        o.skills_have = [w for w in wanted if w.lower() in have]
        o.skills_missing = [w for w in wanted if w.lower() not in have] if have else []
        o.match = round(100 * len(o.skills_have) / len(wanted)) if (wanted and have) else None
        o.for_goal = bool(
            (goal and o.target_role_id and o.target_role_id == goal.role_id)
            or (o.target_domain_id and o.target_domain_id in domains)
            or (o.target_role_id and o.target_role.name.lower() == target_role)
        )
        out.append(o)
    out.sort(key=lambda o: (not o.for_goal, o.match is None, -(o.match or 0), -o.created_at.timestamp()))
    return out
