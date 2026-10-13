"""
Real, derived student metrics. Nothing here is stored or invented:
every value is computed from the student's latest Resume and their
saved goal, and returns None when it can't be computed yet so templates
can show an honest empty state instead of a placeholder number.
"""
from django.utils import timezone

from .skill_matching import analyze_for_profile

# Transparent completeness rubric for the resume score (sums to 100).
# It measures how complete the *parsed* resume is - not "ATS quality" or
# any ML judgement - and the analyzer page explains it in those terms.
RESUME_RUBRIC = [
    # (attribute, label, points, items needed for full points)
    ('skills', 'Skills', 30, 8),
    ('experience', 'Experience', 25, 2),
    ('projects', 'Projects', 20, 2),
    ('education', 'Education', 15, 1),
    ('certifications', 'Certifications', 10, 2),
]


def resume_evaluation(resume):
    """Return (score, rows). Each row: label, points, earned, found, wanted."""
    rows, total = [], 0
    for attr, label, points, wanted in RESUME_RUBRIC:
        found = len(getattr(resume, attr) or [])
        earned = round(points * min(found, wanted) / wanted)
        total += earned
        rows.append(dict(attr=attr, label=label, points=points, earned=earned,
                         found=found, wanted=wanted, fill=round(100 * earned / points)))
    return total, rows


def resume_feedback(rows):
    """Concrete suggestions derived only from what is missing/thin."""
    out = []
    for r in rows:
        if r['found'] == 0:
            out.append(dict(kind='weakness', section=r['label'],
                            text=f"No {r['label'].lower()} were detected. Add a clearly headed {r['label']} section."))
        elif r['found'] < r['wanted']:
            out.append(dict(kind='suggestion', section=r['label'],
                            text=f"{r['found']} {r['label'].lower()} detected; most strong resumes list {r['wanted']} or more."))
        else:
            out.append(dict(kind='strength', section=r['label'],
                            text=f"{r['label']} section is well covered ({r['found']} detected)."))
    return out


def student_snapshot(profile):
    """Everything the dashboard/analyzer/chatbot need, in one place."""
    resume = profile.resumes.first()
    snap = dict(
        resume=resume, has_resume=resume is not None,
        extraction_failed=bool(resume and not resume.skills),
        resume_score=None, resume_rows=[], readiness=None,
        skills_detected=0, detected=[], missing=[], required=[],
        target_label=profile.target_role, priorities={},
    )
    if not resume:
        return snap
    snap['resume_score'], snap['resume_rows'] = resume_evaluation(resume)
    snap['skills_detected'] = len(resume.skills)
    if resume.skills:
        a = analyze_for_profile(profile, resume.skills)
        snap.update(readiness=a['match_percentage'], detected=a['detected'], missing=a['missing'],
                    required=a['required'], target_label=a['label'], priorities=a['priorities'])
    return snap


def recommended_opportunities(detected_skills, kind, limit=3):
    """Published, not-expired opportunities of `kind`, ranked by overlap with
    the student's detected skills. match is None when the posting lists no
    skills (we don't invent a percentage)."""
    from roles.models import Opportunity
    today = timezone.now().date()
    qs = Opportunity.objects.filter(kind=kind, status='open')
    have = {s.lower() for s in detected_skills}
    scored = []
    for o in qs:
        if o.deadline and o.deadline < today:
            continue
        wanted = o.skill_list
        match = round(100 * sum(1 for w in wanted if w.lower() in have) / len(wanted)) if wanted else None
        o.match = match
        scored.append(o)
    scored.sort(key=lambda o: (o.match is None, -(o.match or 0), -o.created_at.timestamp()))
    return scored[:limit]


def sync_profile_metrics(profile):
    """Persist the derived numbers other portals read (staff/admin/alumni
    lists and averages) from the student's real analysis. Zero when there is
    no analysable resume - never a placeholder."""
    snap = student_snapshot(profile)
    fields = dict(
        resume_score=snap['resume_score'] or 0,
        readiness_score=snap['readiness'] or 0,
        skills_acquired=snap['skills_detected'],
        critical_gaps=len(snap['missing']),
        certified_skills=len(snap['detected']),
    )
    changed = [k for k, v in fields.items() if getattr(profile, k) != v]
    if changed:
        for k in changed:
            setattr(profile, k, fields[k])
        profile.save(update_fields=changed)
    return snap
