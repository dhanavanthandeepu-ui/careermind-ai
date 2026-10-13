import io
import shutil
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from careerpath.models import (
    CareerDomain, CareerRole, Company, RoleSkillRequirement, Skill as CatalogSkill,
)
from core.models import LearningResource, Profile, Resume, StudentLearningProgress
from roles.models import (
    AdminDetail, AlumniDetail, Opportunity, ResumeReview, StaffDetail, StudentDetail,
)

TEST_MEDIA = tempfile.mkdtemp(prefix='cm_test_media_')


def make_user(email, role, **extra):
    user = User.objects.create_user(username=email, email=email, password='pw-Test-12345',
                                    first_name=email.split('@')[0].title(), last_name='T', **extra)
    profile = Profile.objects.create(user=user, role=role, university_email=email)
    if role == 'student':
        StudentDetail.objects.create(profile=profile, department='AIML', year='4')
    elif role == 'staff':
        StaffDetail.objects.create(profile=profile)
    elif role == 'alumni':
        AlumniDetail.objects.create(profile=profile)
    elif role == 'admin':
        AdminDetail.objects.create(profile=profile)
    return user


def pdf_bytes(lines):
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    y = 800
    for line in lines:
        c.drawString(60, y, line)
        y -= 18
    c.save()
    return buf.getvalue()


RESUME_LINES = [
    'Jane Doe', 'Skills', 'Python, SQL, Git', 'Education', 'B.Sc. AI and ML, Sacred Heart College',
    'Projects', 'Portfolio website built with Django',
]


class RoleAccessTests(TestCase):
    """The role picked on the login form is never authorization: the
    backend must enforce Profile.role on every portal URL."""

    def setUp(self):
        self.student = make_user('stu@shc.edu', 'student')
        self.staff = make_user('staff@shc.edu', 'staff')
        self.alumni = make_user('alum@shc.edu', 'alumni')
        self.admin = make_user('adm@shc.edu', 'admin')

    def test_anonymous_redirected_to_login(self):
        for name in ('dashboard', 'skill_analysis', 'resume_analyzer', 'learning_roadmap', 'ai_chatbot'):
            r = self.client.get(reverse(name))
            self.assertEqual(r.status_code, 302, name)
            self.assertIn('/login/', r['Location'])

    def test_student_can_open_student_pages(self):
        self.client.force_login(self.student)
        for name in ('dashboard', 'skill_analysis', 'resume_analyzer', 'learning_roadmap', 'ai_chatbot'):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)

    def test_other_roles_are_bounced_off_student_pages(self):
        for user, home in ((self.staff, 'staff:dashboard'), (self.alumni, 'alumni:dashboard'),
                           (self.admin, 'admin_panel:dashboard')):
            self.client.force_login(user)
            for name in ('dashboard', 'skill_analysis', 'resume_analyzer', 'learning_roadmap', 'ai_chatbot'):
                r = self.client.get(reverse(name))
                self.assertRedirects(r, reverse(home), fetch_redirect_response=False, msg_prefix=f'{user} {name}')

    def test_student_api_endpoints_reject_other_roles(self):
        self.client.force_login(self.staff)
        r = self.client.post(reverse('api_resume_upload'), {})
        self.assertEqual(r.status_code, 302)  # bounced, never processed
        self.assertEqual(Resume.objects.count(), 0)

    def test_student_blocked_from_other_portals(self):
        self.client.force_login(self.student)
        for name in ('staff:dashboard', 'alumni:dashboard', 'admin_panel:dashboard',
                     'admin_panel:user_management', 'staff:students'):
            self.assertEqual(self.client.get(reverse(name)).status_code, 403, name)

    def test_staff_and_alumni_cannot_open_each_other_or_admin(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse('alumni:dashboard')).status_code, 403)
        self.assertEqual(self.client.get(reverse('admin_panel:dashboard')).status_code, 403)
        self.client.force_login(self.alumni)
        self.assertEqual(self.client.get(reverse('staff:dashboard')).status_code, 403)
        self.assertEqual(self.client.get(reverse('admin_panel:users')
                                          if False else reverse('admin_panel:user_management')).status_code, 403)

    def test_unapproved_faculty_cannot_use_existing_session(self):
        p = self.staff.profile
        p.is_approved = False
        p.save()
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse('staff:dashboard')).status_code, 403)

    def test_superuser_without_admin_role_reaches_admin_portal(self):
        su = User.objects.create_superuser('root@shc.edu', 'root@shc.edu', 'pw-Test-12345')
        Profile.objects.create(user=su, role='student')  # even with a stale role
        self.client.force_login(su)
        self.assertEqual(self.client.get(reverse('admin_panel:dashboard')).status_code, 200)

    def test_login_ignores_forged_role_field(self):
        r = self.client.post(reverse('login'), {'username': 'stu@shc.edu', 'password': 'pw-Test-12345', 'role': 'admin'})
        self.assertEqual(r.status_code, 200)  # form re-rendered with error, no session
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertEqual(self.client.get(reverse('admin_panel:dashboard')).status_code, 302)


@override_settings(MEDIA_ROOT=TEST_MEDIA)
class ResumeUploadTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA, ignore_errors=True)

    def setUp(self):
        self.user = make_user('stu@shc.edu', 'student')
        self.client.force_login(self.user)

    def upload(self, name, data, ctype='application/pdf'):
        return self.client.post(reverse('api_resume_upload'), {'resume': SimpleUploadedFile(name, data, ctype)})

    def test_no_resume_means_no_scores_anywhere(self):
        html = self.client.get(reverse('dashboard')).content.decode()
        self.assertIn('Upload your resume to begin your career analysis.', html)
        for fake in ('74', '92', '94% Match', 'top 5%', 'Google', 'Goldman'):
            self.assertNotIn(fake, html, fake)
        r = self.client.get(reverse('resume_analyzer'))
        self.assertContains(r, 'Upload your resume to begin your career analysis.')
        self.assertNotContains(r, '<canvas id="scoreGauge"')

    def test_rejects_non_pdf_extension(self):
        r = self.upload('cv.docx', b'PK\x03\x04 not a pdf')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Resume.objects.count(), 0)

    def test_rejects_fake_pdf_with_pdf_extension(self):
        r = self.upload('cv.pdf', b'<html>this is not a pdf</html>')
        self.assertEqual(r.status_code, 400)
        self.assertIn('not a valid PDF', r.json()['error'])
        self.assertEqual(Resume.objects.count(), 0)

    def test_rejects_oversized_file(self):
        r = self.upload('cv.pdf', b'%PDF-' + b'0' * (5 * 1024 * 1024 + 10))
        self.assertEqual(r.status_code, 400)
        self.assertIn('too large', r.json()['error'])
        self.assertEqual(Resume.objects.count(), 0)

    def test_valid_pdf_is_parsed_scored_and_attached_to_student(self):
        r = self.upload('cv.pdf', pdf_bytes(RESUME_LINES))
        self.assertEqual(r.status_code, 200, r.content)
        data = r.json()
        self.assertEqual({s.lower() for s in data['skills']}, {'python', 'sql', 'git'})
        resume = Resume.objects.get()
        self.assertEqual(resume.profile.user, self.user)
        # rubric: skills 3/8 -> 11, education 1/1 -> 15, projects 1/2 -> 10
        self.assertEqual(data['resume_score'], 36)
        self.assertEqual(self.client.get(reverse('resume_analyzer')).status_code, 200)

    def test_new_profiles_start_at_zero_not_invented_scores(self):
        prof = self.user.profile
        self.assertEqual((prof.resume_score, prof.readiness_score, prof.skills_acquired, prof.critical_gaps), (0, 0, 0, 0))
        r = self.client.get(reverse('resume_analyzer'))
        self.assertNotContains(r, '>92<')

    def test_stored_metrics_follow_the_real_analysis(self):
        self.upload('cv.pdf', pdf_bytes(RESUME_LINES))
        prof = Profile.objects.get(user=self.user)
        self.assertEqual(prof.resume_score, 36)           # same rubric score the student sees
        self.assertEqual(prof.skills_acquired, 3)
        self.assertGreaterEqual(prof.critical_gaps, 0)

    def test_feedback_pdf_needs_a_resume(self):
        r = self.client.get(reverse('feedback_pdf'))
        self.assertRedirects(r, reverse('resume_analyzer'), fetch_redirect_response=False)
        self.upload('cv.pdf', pdf_bytes(RESUME_LINES))
        r = self.client.get(reverse('feedback_pdf'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')

    def test_request_review_creates_single_pending_review(self):
        r = self.client.post(reverse('api_request_resume_review'))
        self.assertEqual(r.status_code, 400)  # no resume yet
        self.upload('cv.pdf', pdf_bytes(RESUME_LINES))
        self.assertEqual(self.client.post(reverse('api_request_resume_review')).status_code, 200)
        self.assertEqual(self.client.post(reverse('api_request_resume_review')).status_code, 400)
        self.assertEqual(ResumeReview.objects.filter(student=self.user, status='pending').count(), 1)


@override_settings(MEDIA_ROOT=TEST_MEDIA)
class GoalAndSkillGapTests(TestCase):
    """One source of truth: the saved goal drives Skill Analysis + Learning Path."""

    def setUp(self):
        self.user = make_user('stu@shc.edu', 'student')
        self.profile = self.user.profile
        self.client.force_login(self.user)
        self.domain = CareerDomain.objects.create(name='Data Analytics')
        self.role = CareerRole.objects.create(domain=self.domain, name='Data Analyst')
        self.company = Company.objects.create(name='Acme')
        for name, prio in (('SQL', 'critical'), ('Tableau', 'high'), ('Git', 'low')):
            sk, _ = CatalogSkill.objects.get_or_create(name=name)
            RoleSkillRequirement.objects.create(company=self.company, role=self.role, skill=sk, priority=prio)
        Resume.objects.create(profile=self.profile, file='resumes/x.pdf', skills=['Python', 'Git'],
                              education=['BSc'])

    def save_goal(self):
        return self.client.post(reverse('careerpath:set_goal'), {
            'domain': self.domain.id, 'role': self.role.id, 'company': self.company.id, 'timeline_months': 6})

    def test_saving_goal_syncs_target_role_and_skill_rows(self):
        self.assertEqual(self.profile.target_role, 'Cloud Solutions Architect')  # legacy default
        r = self.save_goal()
        self.assertEqual(r.status_code, 302)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.target_role, 'Data Analyst')
        rows = {s.name: s for s in self.profile.skills.all()}
        self.assertEqual(set(rows), {'SQL', 'Tableau', 'Git'})          # DB requirements, not the legacy dict
        self.assertEqual(rows['Git'].current, 100)                       # detected
        self.assertEqual(rows['SQL'].current, 0)                         # gap
        self.assertEqual(rows['SQL'].priority, 'high')                   # critical -> high

    def test_learning_path_follows_goal_and_students_get_different_resources(self):
        LearningResource.objects.create(skill='SQL', title='SQL basics', youtube_url='https://www.youtube.com/watch?v=aaaaaaaaaaa')
        LearningResource.objects.create(skill='Tableau', title='Tableau intro', youtube_url='https://www.youtube.com/watch?v=bbbbbbbbbbb')
        self.save_goal()
        html = self.client.get(reverse('learning_roadmap')).content.decode()
        self.assertIn('SQL basics', html)
        self.assertIn('Tableau intro', html)
        self.assertNotIn('Python tutorial', html)

        # a second student with a different resume gets different gaps/resources
        other = make_user('other@shc.edu', 'student')
        Resume.objects.create(profile=other.profile, file='resumes/y.pdf', skills=['SQL', 'Tableau', 'Git'])
        self.client.force_login(other)
        html2 = self.client.get(reverse('learning_roadmap')).content.decode()
        self.assertNotIn('SQL basics', html2)
        self.assertNotIn('Tableau intro', html2)

    def test_skill_with_no_resource_shows_honest_empty_message(self):
        self.save_goal()  # no LearningResource rows exist at all
        r = self.client.get(reverse('learning_roadmap'))
        self.assertContains(r, 'No learning resources available for this skill yet.')

    def test_without_goal_legacy_role_list_still_works(self):
        self.profile.target_role = 'Backend Developer'
        self.profile.save()
        Resume.objects.create(profile=self.profile, file='resumes/z.pdf', skills=['Python', 'Git', 'SQL'])
        r = self.client.get(reverse('skill_analysis'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context['snap']['required'], ['Python', 'Django', 'SQL', 'Git', 'REST API'])


class LearningProgressTests(TestCase):
    def setUp(self):
        self.user = make_user('stu@shc.edu', 'student')
        self.profile = self.user.profile
        self.profile.target_role = 'Data Analyst'
        self.profile.save()
        Resume.objects.create(profile=self.profile, file='resumes/x.pdf', skills=['Python'])
        self.res = [LearningResource.objects.create(
            skill='SQL', title=f'SQL {i}', order=i, youtube_url='https://www.youtube.com/watch?v=aaaaaaaaaaa')
            for i in range(1, 6)]
        self.client.force_login(self.user)

    def test_progress_is_calculated_from_completed_tasks(self):
        for r in self.res[:2]:
            resp = self.client.post(reverse('api_learning_progress', args=[r.id]), {'status': 'completed'})
            self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual((data['completed_resources'], data['total_resources'], data['overall_progress']), (2, 5, 40))
        # un-checking lowers it again
        data = self.client.post(reverse('api_learning_progress', args=[self.res[0].id]), {'status': 'not_started'}).json()
        self.assertEqual(data['overall_progress'], 20)

    def test_progress_is_per_student(self):
        self.client.post(reverse('api_learning_progress', args=[self.res[0].id]), {'status': 'completed'})
        other = make_user('other@shc.edu', 'student')
        self.assertEqual(StudentLearningProgress.objects.filter(student=other.profile).count(), 0)

    def test_invalid_status_rejected(self):
        r = self.client.post(reverse('api_learning_progress', args=[self.res[0].id]), {'status': 'hacked'})
        self.assertEqual(r.status_code, 400)

    def test_get_not_allowed(self):
        self.assertEqual(self.client.get(reverse('api_learning_progress', args=[self.res[0].id])).status_code, 405)


class DashboardRecommendationTests(TestCase):
    def setUp(self):
        self.user = make_user('stu@shc.edu', 'student')
        Resume.objects.create(profile=self.user.profile, file='resumes/x.pdf', skills=['Python', 'SQL'])
        self.client.force_login(self.user)

    def test_only_published_opportunities_are_recommended_with_real_match(self):
        Opportunity.objects.create(title='Data Intern', company='Acme', kind='internship', status='open',
                                   skills='Python, SQL, Spark, Tableau')
        Opportunity.objects.create(title='Secret Pending Job', company='Acme', kind='job', status='pending')
        Opportunity.objects.create(title='Rejected Job', company='Acme', kind='job', status='rejected')
        html = self.client.get(reverse('dashboard')).content.decode()
        self.assertIn('Data Intern', html)
        self.assertIn('50%', html)                       # 2 of 4 skills
        self.assertNotIn('Secret Pending Job', html)
        self.assertNotIn('Rejected Job', html)

    def test_expired_opportunities_hidden(self):
        import datetime
        from django.utils import timezone
        Opportunity.objects.create(title='Old Job', company='Acme', kind='job', status='open',
                                   deadline=timezone.now().date() - datetime.timedelta(days=1))
        self.assertNotContains(self.client.get(reverse('dashboard')), 'Old Job')


class ChatbotTests(TestCase):
    def setUp(self):
        self.user = make_user('stu@shc.edu', 'student')
        self.client.force_login(self.user)

    def test_no_resume_reply_does_not_invent_numbers(self):
        r = self.client.post(reverse('chatbot_reply'), {'message': 'what is my readiness'})
        self.assertIn('Upload your resume', r.json()['reply'])
        self.assertNotIn('74', r.json()['reply'])

    def test_reply_uses_real_gaps(self):
        self.user.profile.target_role = 'Backend Developer'
        self.user.profile.save()
        Resume.objects.create(profile=self.user.profile, file='resumes/x.pdf', skills=['Python', 'Git'])
        reply = self.client.post(reverse('chatbot_reply'), {'message': 'skill gaps?'}).json()['reply']
        self.assertIn('Django', reply)
        self.assertNotIn('Python', reply)
