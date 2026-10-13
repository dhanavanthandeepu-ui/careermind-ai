"""
Matches a student's resume-detected skills against the required skill
set for their target career role.

This intentionally reuses the existing `Skill` model (name, category,
current, target, status, priority) instead of introducing a new one:
- a DETECTED required skill becomes a Skill row with current=100/target=100
- a MISSING required skill (a real skill gap) becomes current=0/target=100

That means the existing "Detailed Skill Inventory" table on the Skill
Analysis page — which already reads `profile.skills.all()` — needs no
template changes to display real data; only WHEN and HOW those rows
get populated has changed (see apply_skill_match_to_profile below).

No skill is ever invented: "detected" means the resume parser actually
found that exact skill name in the uploaded resume (see
core/resume_parser.py); "missing" means it didn't.
"""
from .models import Skill

# Target role -> the skills CareerMind checks for that role. Names here
# should match the canonical forms core/resume_parser.py normalizes
# extracted skills to (see CANONICAL_SKILLS there), since matching is a
# plain case-insensitive comparison — no fuzzy/AI matching involved.
ROLE_SKILL_REQUIREMENTS = {
    "Data Analyst": ["Python", "SQL", "Excel", "Power BI", "Statistics"],
    "Cloud Solutions Architect": ["AWS", "Azure", "Kubernetes", "Terraform", "Linux", "Python"],
    "Machine Learning Engineer": ["Python", "Machine Learning", "TensorFlow", "PyTorch", "SQL", "Statistics"],
    "Backend Developer": ["Python", "Django", "SQL", "Git", "REST API"],
    "Frontend Developer": ["JavaScript", "React", "HTML", "CSS", "Git"],
    "DevOps Engineer": ["Docker", "Kubernetes", "Jenkins", "Linux", "CI/CD", "AWS"],
    "Senior Data Engineer": ["Python", "SQL", "AWS", "Kafka", "CI/CD"],
    "AI Solution Architect": ["Python", "Machine Learning", "AWS", "Kubernetes", "SQL"],
}

# Used only when the student's target_role isn't one of the roles
# above (target_role is free text on signup, so this can happen).
DEFAULT_REQUIRED_SKILLS = ["Python", "SQL", "Git", "Communication"]


def get_required_skills(target_role: str):
    """The list of skills CareerMind checks for a given target role."""
    return ROLE_SKILL_REQUIREMENTS.get(target_role, DEFAULT_REQUIRED_SKILLS)


_PRIORITY_MAP = {'critical': 'high', 'high': 'high', 'medium': 'medium', 'low': 'low'}


def resolve_requirements(profile):
    """
    The single place that decides "which skills does this student need?".

    1. If the student has saved a Career Goal AND the admin-managed
       RoleSkillRequirement table has rows for that (company, role), those
       database rows win (each with its own priority).
    2. Otherwise fall back to the original hardcoded per-role list keyed by
       Profile.target_role, exactly as before.

    Returns dict(required=[names], priorities={lowercase name: core priority},
    source='goal'|'legacy', label=str).
    """
    from careerpath.models import RoleSkillRequirement, StudentCareerGoal

    goal = StudentCareerGoal.objects.filter(profile=profile).select_related('role', 'company').first()
    if goal:
        order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
        reqs = sorted(
            RoleSkillRequirement.objects.filter(company=goal.company, role=goal.role).select_related('skill'),
            key=lambda r: (order.get(r.priority, 4), r.skill.name),
        )
        if reqs:
            return dict(
                required=[r.skill.name for r in reqs],
                priorities={r.skill.name.lower(): _PRIORITY_MAP.get(r.priority, 'medium') for r in reqs},
                source='goal',
                label=f"{goal.role.name} at {goal.company.name}",
            )
    return dict(
        required=list(get_required_skills(profile.target_role)),
        priorities={},
        source='legacy',
        label=profile.target_role,
    )


def analyze_skill_match(detected_skills, target_role: str, required=None) -> dict:
    """
    Compare a resume's detected skills against a target role's required
    skills. `detected_skills` should be the (already cleaned/normalized)
    list from Resume.skills.

    Returns:
      required          -- full required-skill list for the role
      detected          -- required skills that WERE found in the resume
      missing           -- required skills that were NOT found (skill gaps)
      match_percentage  -- len(detected) / len(required) as 0-100
    """
    if required is None:
        required = get_required_skills(target_role)
    detected_lookup = {s.strip().lower() for s in detected_skills}

    detected = [r for r in required if r.strip().lower() in detected_lookup]
    missing = [r for r in required if r.strip().lower() not in detected_lookup]

    match_percentage = round(100 * len(detected) / len(required)) if required else 0

    return {
        "required": required,
        "detected": detected,
        "missing": missing,
        "match_percentage": match_percentage,
    }


def analyze_for_profile(profile, detected_skills) -> dict:
    """analyze_skill_match() using whatever resolve_requirements() picks for
    this student. Adds 'priorities' and 'label' to the usual result."""
    reqs = resolve_requirements(profile)
    result = analyze_skill_match(detected_skills, profile.target_role, required=reqs['required'])
    result['priorities'] = reqs['priorities']
    result['source'] = reqs['source']
    result['label'] = reqs['label']
    return result


def refresh_student_analysis(profile) -> bool:
    """Recompute and persist the student's Skill rows from their latest
    resume against their current goal/role. Returns False if there is no
    resume with detected skills (nothing is changed in that case)."""
    resume = profile.resumes.first()
    if not resume or not resume.skills:
        return False
    apply_skill_match_to_profile(profile, analyze_for_profile(profile, resume.skills))
    return True


def apply_skill_match_to_profile(profile, analysis: dict) -> None:
    """
    Persist a skill-match analysis into the profile's Skill rows.

    Wipes any Skill rows from a previous resume/analysis first, so a
    new resume upload always fully replaces the old analysis (no stale
    skills linger from a resume the student has since replaced).
    """
    profile.skills.all().delete()

    for name in analysis["detected"]:
        Skill.objects.create(
            profile=profile, name=name, category="technical",
            current=100, target=100, status="growing", priority="low",
        )
    for name in analysis["missing"]:
        Skill.objects.create(
            profile=profile, name=name, category="technical",
            current=0, target=100, status="stable",
            priority=analysis.get("priorities", {}).get(name.lower(), "high"),
        )
