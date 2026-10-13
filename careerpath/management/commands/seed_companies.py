"""
Seeds the Company / CareerDomain / CareerRole / Skill / RoleSkillRequirement
tables with a starting, EDITABLE dataset.

IMPORTANT — what this data is and isn't:
The per-role skill lists below are a generic, industry-standard baseline
(the same skill sets CareerMind already used role-only, in
core/skill_matching.py's ROLE_SKILL_REQUIREMENTS) applied identically
across every seeded company. This is NOT a claim that, say, TCS has
published exactly these requirements — every seeded row's `source`
field says so explicitly, and an Admin is expected to review/edit
per-company requirements over time from this starting point.

Safe to re-run: uses get_or_create throughout, so re-running only fills
in anything missing and never duplicates rows.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from careerpath.models import CareerDomain, CareerRole, Company, RoleSkillRequirement, Skill

COMPANIES = [
    "TCS", "Infosys", "Wipro", "Accenture", "Cognizant", "Capgemini",
    "HCLTech", "Tech Mahindra", "LTIMindtree", "Zoho", "Freshworks",
    "IBM", "Deloitte", "EY", "Genpact",
]

# domain -> [role, ...]
DOMAINS_AND_ROLES = {
    "Web Development": ["Frontend Developer", "Backend Developer", "Full Stack Developer"],
    "Data Analytics": ["Data Analyst"],
    "Data Science / AI-ML": ["AI/ML Engineer"],
}

# role -> [(skill, priority), ...] — the generic baseline requirement set.
ROLE_SKILLS = {
    "Frontend Developer": [
        ("HTML", "critical"), ("CSS", "critical"), ("JavaScript", "critical"),
        ("React", "high"), ("Git", "medium"),
    ],
    "Backend Developer": [
        ("Python", "critical"), ("Django", "high"), ("SQL", "high"),
        ("Git", "medium"), ("REST API", "medium"),
    ],
    "Full Stack Developer": [
        ("JavaScript", "critical"), ("React", "high"), ("Python", "high"),
        ("SQL", "medium"), ("Git", "medium"),
    ],
    "Data Analyst": [
        ("SQL", "critical"), ("Excel", "critical"), ("Python", "high"),
        ("Power BI", "high"), ("Statistics", "medium"),
    ],
    "AI/ML Engineer": [
        ("Python", "critical"), ("Machine Learning", "critical"),
        ("TensorFlow", "high"), ("PyTorch", "medium"), ("SQL", "medium"),
    ],
}

SEED_SOURCE = "Generic industry baseline (not company-verified) — update via Admin."


class Command(BaseCommand):
    help = "Seeds companies, career domains/roles, the skill catalog and role-skill requirements."

    @transaction.atomic
    def handle(self, *args, **options):
        company_objs = []
        for name in COMPANIES:
            company, created = Company.objects.get_or_create(name=name)
            company_objs.append(company)
            self.stdout.write(f"{'Created' if created else 'Exists'}: Company {name}")

        role_objs = []
        for domain_name, role_names in DOMAINS_AND_ROLES.items():
            domain, created = CareerDomain.objects.get_or_create(name=domain_name)
            self.stdout.write(f"{'Created' if created else 'Exists'}: Domain {domain_name}")
            for role_name in role_names:
                role, created = CareerRole.objects.get_or_create(domain=domain, name=role_name)
                role_objs.append(role)
                self.stdout.write(f"  {'Created' if created else 'Exists'}: Role {role_name}")

        skill_cache = {}
        req_created_count = 0
        for role in role_objs:
            skill_priorities = ROLE_SKILLS.get(role.name, [])
            for company in company_objs:
                for skill_name, priority in skill_priorities:
                    if skill_name not in skill_cache:
                        skill_obj, _ = Skill.objects.get_or_create(name=skill_name)
                        skill_cache[skill_name] = skill_obj
                    skill_obj = skill_cache[skill_name]

                    _req, created = RoleSkillRequirement.objects.get_or_create(
                        company=company, role=role, skill=skill_obj,
                        defaults=dict(priority=priority, source=SEED_SOURCE),
                    )
                    if created:
                        req_created_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"Done. {len(company_objs)} companies, {len(role_objs)} roles, "
            f"{len(skill_cache)} distinct skills, {req_created_count} new requirement rows."
        ))
