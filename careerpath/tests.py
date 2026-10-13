from django.contrib.auth.models import User
from django.test import TestCase

from core.models import Profile

from .models import CareerDomain, CareerRole, Company, RoleSkillRequirement, Skill, StudentCareerGoal
from .services import (
    build_or_refresh_roadmap, classify_resume_domain, compute_skill_gap, generate_roadmap_plan,
)


class DomainClassificationTests(TestCase):
    def test_no_skills_returns_none(self):
        domain, reason = classify_resume_domain([])
        self.assertIsNone(domain)
        self.assertIn("Upload a resume", reason)

    def test_clear_frontend_signal(self):
        domain, reason = classify_resume_domain(["HTML", "CSS", "JavaScript", "React"])
        self.assertEqual(domain, "Frontend Development")

    def test_weak_signal_returns_none(self):
        domain, reason = classify_resume_domain(["Communication"])
        self.assertIsNone(domain)


class SkillGapTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(username='student1', password='pass12345')
        self.profile = Profile.objects.create(user=user, role='student')
        self.company = Company.objects.create(name='TCS')
        self.domain = CareerDomain.objects.create(name='Data Analytics')
        self.role = CareerRole.objects.create(domain=self.domain, name='Data Analyst')
        for name, priority in [("SQL", "critical"), ("Excel", "critical"), ("Power BI", "high")]:
            skill = Skill.objects.create(name=name)
            RoleSkillRequirement.objects.create(company=self.company, role=self.role, skill=skill, priority=priority)

    def test_no_requirements_for_unseeded_pair(self):
        other_role = CareerRole.objects.create(domain=self.domain, name='Unrelated Role')
        result = compute_skill_gap(["SQL"], self.company, other_role)
        self.assertFalse(result['has_requirements'])
        self.assertEqual(result['match_percentage'], 0)

    def test_partial_match(self):
        result = compute_skill_gap(["SQL", "Python"], self.company, self.role)
        self.assertTrue(result['has_requirements'])
        detected_names = [r.skill.name for r in result['current']]
        gap_names = [r.skill.name for r in result['gaps']]
        self.assertEqual(detected_names, ["SQL"])
        self.assertEqual(set(gap_names), {"Excel", "Power BI"})
        self.assertEqual(result['match_percentage'], 33)

    def test_roadmap_generation_from_gaps(self):
        goal = StudentCareerGoal.objects.create(
            profile=self.profile, domain=self.domain, role=self.role,
            company=self.company, timeline_months=6,
        )
        result = compute_skill_gap([], self.company, self.role)
        roadmap = build_or_refresh_roadmap(goal, result['gaps'])
        self.assertTrue(roadmap.milestones.exists())
        # Final month is always placement prep when there's more than 1 month.
        last = roadmap.milestones.order_by('-month_number').first()
        self.assertEqual(last.month_number, 6)
        self.assertEqual(last.title, "Placement Preparation")


class RoadmapPlanTests(TestCase):
    def test_empty_gaps_still_returns_final_month(self):
        plan = generate_roadmap_plan([], timeline_months=3)
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0]['month_number'], 3)

    def test_single_month_timeline(self):
        plan = generate_roadmap_plan([], timeline_months=1)
        self.assertEqual(plan[0]['month_number'], 1)
