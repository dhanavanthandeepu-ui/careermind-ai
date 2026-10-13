"""
Business logic for the career-goal / placement-roadmap flow.

Everything here reads real data (Resume.skills, the RoleSkillRequirement
table) and computes results deterministically. There is no ML model and
none is claimed — the domain classifier is an explicit, transparent
weighted keyword match (see DOMAIN_SIGNAL_SKILLS below), same spirit as
the existing core/skill_matching.py.
"""
from .models import RoleSkillRequirement, RoadmapMilestone

# ---------------------------------------------------------------------------
# 1. Resume -> probable career domain (transparent rule-based classifier)
# ---------------------------------------------------------------------------

# Domain name -> skills that count as evidence for it, each with a weight.
# Skill names here should match the canonical forms core/resume_parser.py
# normalizes resume skills to (CANONICAL_SKILLS), since matching is a
# plain case-insensitive comparison. This is a starting, editable set —
# not a claim of exhaustive coverage.
DOMAIN_SIGNAL_SKILLS = {
    "Frontend Development": {"HTML": 2, "CSS": 2, "JavaScript": 3, "React": 3, "Angular": 3, "Vue.js": 3, "TypeScript": 2},
    "Backend Development": {"Python": 2, "Django": 3, "Flask": 2, "Java": 2, "Spring": 2, "Spring Boot": 2, "SQL": 1, "REST API": 2, "Node.js": 2},
    "Full Stack Development": {"React": 2, "Node.js": 2, "JavaScript": 2, "Django": 2, "SQL": 1, "HTML": 1, "CSS": 1},
    "Data Analytics": {"SQL": 3, "Excel": 3, "Power BI": 3, "Tableau": 3, "Statistics": 2, "Python": 1},
    "Data Science / AI-ML": {"Machine Learning": 3, "Python": 2, "TensorFlow": 3, "PyTorch": 3, "Pandas": 2, "NumPy": 2, "Deep Learning": 3, "scikit-learn": 3, "Statistics": 1},
    "Cloud Engineering": {"AWS": 3, "Azure": 3, "GCP": 3, "Kubernetes": 3, "Terraform": 3, "Docker": 2, "Linux": 1},
    "DevOps": {"Docker": 3, "Kubernetes": 3, "Jenkins": 3, "CI/CD": 3, "Ansible": 2, "Terraform": 2, "Linux": 1},
    "Cybersecurity": {"Linux": 1, "Network Security": 3, "Penetration Testing": 3, "Cryptography": 3},
}

DOMAIN_CLASSIFICATION_MIN_SCORE = 2  # below this, evidence is too thin to name a domain


def classify_resume_domain(detected_skills):
    """
    Returns (domain_name, explanation) or (None, reason) if there isn't
    enough evidence. Never guesses a domain from zero/near-zero signal —
    that would be exactly the "fake AI claim" the platform must avoid.
    """
    if not detected_skills:
        return None, "Upload a resume with a Skills section to detect a career profile."

    skills_lookup = {s.strip().lower() for s in detected_skills}
    scores = {}
    matched_by_domain = {}
    for domain, weights in DOMAIN_SIGNAL_SKILLS.items():
        score = 0
        matched = []
        for skill, weight in weights.items():
            if skill.lower() in skills_lookup:
                score += weight
                matched.append(skill)
        if score:
            scores[domain] = score
            matched_by_domain[domain] = matched

    if not scores:
        return None, "No recognizable domain signals found in your extracted skills yet."

    best_domain = max(scores, key=scores.get)
    if scores[best_domain] < DOMAIN_CLASSIFICATION_MIN_SCORE:
        return None, "Not enough matching skills yet to confidently detect a career profile."

    matched = matched_by_domain[best_domain]
    explanation = "Based on your resume skills: " + ", ".join(matched[:5])
    return best_domain, explanation


# ---------------------------------------------------------------------------
# 2. Company + role aware skill-gap calculation
# ---------------------------------------------------------------------------

def get_role_requirements(company, role):
    """All RoleSkillRequirement rows for this (company, role), ordered
    Critical -> Low. Empty queryset (not an exception) if nothing is
    seeded yet for this pair — callers must handle that explicitly
    rather than inventing requirements."""
    order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
    reqs = list(RoleSkillRequirement.objects.filter(company=company, role=role).select_related('skill'))
    reqs.sort(key=lambda r: order.get(r.priority, 4))
    return reqs


def compute_skill_gap(detected_skills, company, role):
    """
    Compares the student's resume-detected skills against the real,
    database-stored requirements for (company, role).

    Returns a dict with:
      has_requirements -- False if nothing is seeded for this pair yet
      current          -- requirement rows the student already has
      gaps             -- requirement rows the student is missing, each
                           annotated with .current_status / .target_status
      match_percentage -- len(current) / len(all) as 0-100 (0 if no
                           requirements exist — never a placeholder number)
    """
    requirements = get_role_requirements(company, role)
    if not requirements:
        return dict(has_requirements=False, current=[], gaps=[], match_percentage=0)

    skills_lookup = {s.strip().lower() for s in detected_skills}
    current, gaps = [], []
    for req in requirements:
        req.current_status = "Detected" if req.skill.name.lower() in skills_lookup else "Not Detected"
        req.target_status = "Required"
        if req.current_status == "Detected":
            current.append(req)
        else:
            gaps.append(req)

    match_percentage = round(100 * len(current) / len(requirements))
    return dict(has_requirements=True, current=current, gaps=gaps, match_percentage=match_percentage)


# ---------------------------------------------------------------------------
# 3. Timeline-based roadmap generation
# ---------------------------------------------------------------------------

FINAL_MONTH_TASKS = [
    "Build or finish a portfolio project demonstrating your target-role skills",
    "Update your resume to highlight the skills you closed this roadmap",
    "Complete a mock interview focused on your target role",
    "Revise aptitude / fundamentals for placement rounds",
]


def generate_roadmap_plan(gaps, timeline_months):
    """
    Deterministically buckets the missing-skill requirements (already
    priority-sorted by compute_skill_gap) across the available months,
    critical/high skills first, reserving the final month for
    portfolio + interview + placement prep. Returns a list of
    {month_number, title, tasks} dicts — no month is ever left with
    invented content, and no skill is ever added that wasn't a real gap.
    """
    plan = []
    if timeline_months < 1:
        return plan

    prep_months = max(1, timeline_months - 1) if timeline_months > 1 else timeline_months
    gap_names = [g.skill.name for g in gaps]

    if not gap_names:
        # No gaps at all: still give the final placement-prep month.
        plan.append(dict(month_number=timeline_months, title="Placement Preparation", tasks=list(FINAL_MONTH_TASKS)))
        return plan

    # Spread gap skills evenly across the prep months (1+ skill/month).
    buckets = [[] for _ in range(prep_months)]
    for i, name in enumerate(gap_names):
        buckets[i % prep_months].append(name)

    for month_index, skills_this_month in enumerate(buckets, start=1):
        if not skills_this_month:
            continue
        tasks = [f"Learn / strengthen: {s}" for s in skills_this_month]
        plan.append(dict(
            month_number=month_index,
            title=" & ".join(skills_this_month),
            tasks=tasks,
        ))

    if timeline_months > 1:
        plan.append(dict(month_number=timeline_months, title="Placement Preparation", tasks=list(FINAL_MONTH_TASKS)))

    return plan


def build_or_refresh_roadmap(goal, gaps):
    """Creates the Roadmap + RoadmapMilestone rows for a goal, or replaces
    them if the goal (role/company/timeline) has since changed. Existing
    is_completed progress is intentionally NOT preserved across a goal
    change, since a changed goal means a genuinely different plan."""
    from .models import Roadmap

    plan = generate_roadmap_plan(gaps, goal.timeline_months)

    roadmap, _created = Roadmap.objects.get_or_create(goal=goal)
    roadmap.milestones.all().delete()
    for item in plan:
        RoadmapMilestone.objects.create(
            roadmap=roadmap,
            month_number=item['month_number'],
            title=item['title'],
            tasks=item['tasks'],
        )
    return roadmap


# ---------------------------------------------------------------------------
# 4. Overall career feedback + summary
# ---------------------------------------------------------------------------

def build_career_feedback(profile, goal, gap_result, roadmap):
    """
    Builds the "Overall Career Feedback" data, entirely from real
    inputs. Any piece that can't be computed yet is explicitly marked
    'Not enough data yet' rather than filled with a generic line.
    """
    feedback = {
        "goal": goal,
        "readiness": gap_result['match_percentage'] if gap_result['has_requirements'] else None,
        "strengths": [r.skill.name for r in gap_result.get('current', [])],
        "gaps": [r.skill.name for r in gap_result.get('gaps', [])],
        "critical_gaps": [r.skill.name for r in gap_result.get('gaps', []) if r.priority == 'critical'],
        "roadmap_progress": roadmap.progress_percentage if roadmap else None,
        "milestones_done": roadmap.milestones.filter(is_completed=True).count() if roadmap else 0,
        "milestones_total": roadmap.milestones.count() if roadmap else 0,
        "next_action": None,
        "has_requirements": gap_result['has_requirements'],
    }

    if not gap_result['has_requirements']:
        feedback["next_action"] = "Not enough data yet — no skill requirements are on file for this company/role yet."
    else:
        next_gap = next((r for r in gap_result['gaps']), None)
        if next_gap:
            feedback["next_action"] = f"Focus on {next_gap.skill.name} next ({next_gap.get_priority_display()} priority)."
        else:
            feedback["next_action"] = "All tracked requirements for this role are currently met — keep building your portfolio."

    return feedback


def build_career_summary(profile, goal, feedback):
    """The short natural-language 'Your Career Summary' paragraph, built
    only from fields that are actually populated."""
    if not goal:
        return "Set a career goal to generate your personalized summary."

    parts = [f"You are targeting {goal.role.name} at {goal.company.name} within {goal.timeline_months} months."]

    if feedback["strengths"]:
        parts.append("Your current profile shows strength in " + ", ".join(feedback["strengths"][:3]) + ".")

    if feedback["gaps"]:
        parts.append("Your highest-priority gaps are " + ", ".join(feedback["gaps"][:3]) + ".")
    elif feedback["has_requirements"]:
        parts.append("You currently meet all tracked requirements for this role.")

    if feedback["roadmap_progress"] is not None:
        parts.append(f"Your current roadmap progress is {feedback['roadmap_progress']}%.")

    if feedback["next_action"]:
        parts.append(feedback["next_action"])

    return " ".join(parts)
