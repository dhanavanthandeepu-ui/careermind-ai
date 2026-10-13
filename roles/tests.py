from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.tests import make_user
from roles.models import GuidanceRequest, Opportunity


class StaffScopeTests(TestCase):
    def setUp(self):
        self.staff = make_user('staff@shc.edu', 'staff')
        self.student = make_user('stu@shc.edu', 'student')
        self.admin = make_user('adm@shc.edu', 'admin')
        self.client.force_login(self.staff)

    def test_staff_can_open_student_profile(self):
        self.assertEqual(self.client.get(reverse('staff:student_profile', args=[self.student.id])).status_code, 200)

    def test_staff_cannot_open_non_student_accounts(self):
        self.assertEqual(self.client.get(reverse('staff:student_profile', args=[self.admin.id])).status_code, 404)
        self.assertEqual(self.client.get(reverse('staff:student_profile', args=[self.staff.id])).status_code, 404)

    def test_guidance_status_must_be_a_real_status(self):
        gr = GuidanceRequest.objects.create(student=self.student, topic='Interview prep')
        r = self.client.post(reverse('staff:career_guidance'), {'request_id': gr.id, 'status': '<script>x</script>'})
        self.assertEqual(r.status_code, 400)
        gr.refresh_from_db()
        self.assertEqual(gr.status, 'open')
        r = self.client.post(reverse('staff:career_guidance'), {'request_id': gr.id, 'status': 'resolved'})
        self.assertEqual(r.status_code, 302)
        gr.refresh_from_db()
        self.assertEqual((gr.status, gr.staff), ('resolved', self.staff))


class ApprovalFlowTests(TestCase):
    def setUp(self):
        self.alumni = make_user('alum@shc.edu', 'alumni')
        self.admin = make_user('adm@shc.edu', 'admin')
        self.student = make_user('stu@shc.edu', 'student')

    def post_job(self, **extra):
        self.client.force_login(self.alumni)
        data = dict(title='Backend Intern', company='Acme', kind='internship', location='Chennai')
        data.update(extra)
        return self.client.post(reverse('alumni:opportunities'), data)

    def test_alumni_post_starts_pending_and_is_hidden_from_students(self):
        self.post_job()
        opp = Opportunity.objects.get()
        self.assertEqual((opp.status, opp.posted_by_alumni), ('pending', self.alumni))
        self.client.force_login(self.student)
        self.assertNotContains(self.client.get(reverse('dashboard')), 'Backend Intern')

    def test_forged_status_field_is_ignored(self):
        self.post_job(status='open')
        self.assertEqual(Opportunity.objects.get().status, 'pending')

    def test_invalid_post_is_rejected(self):
        self.post_job(title='  ')
        self.post_job(kind='hacker')
        self.assertEqual(Opportunity.objects.count(), 0)

    def test_admin_approve_publishes_and_students_see_it(self):
        self.post_job()
        opp = Opportunity.objects.get()
        self.client.force_login(self.admin)
        self.client.post(reverse('admin_panel:opportunities'), {'opp_id': opp.id, 'action': 'approve'})
        opp.refresh_from_db()
        self.assertEqual((opp.status, opp.reviewed_by), ('open', self.admin))
        self.assertIsNotNone(opp.reviewed_at)
        self.client.force_login(self.student)
        self.assertContains(self.client.get(reverse('dashboard')), 'Backend Intern')

    def test_admin_reject_is_distinct_from_close(self):
        self.post_job()
        opp = Opportunity.objects.get()
        self.client.force_login(self.admin)
        self.client.post(reverse('admin_panel:opportunities'), {'opp_id': opp.id, 'action': 'reject'})
        opp.refresh_from_db()
        self.assertEqual(opp.status, 'rejected')

    def test_non_admins_cannot_approve(self):
        self.post_job()
        opp = Opportunity.objects.get()
        self.client.force_login(self.alumni)
        r = self.client.post(reverse('admin_panel:opportunities'), {'opp_id': opp.id, 'action': 'approve'})
        self.assertEqual(r.status_code, 403)
        opp.refresh_from_db()
        self.assertEqual(opp.status, 'pending')


class AdminUserManagementTests(TestCase):
    def setUp(self):
        self.admin = make_user('adm@shc.edu', 'admin')
        self.student = make_user('stu@shc.edu', 'student')
        self.client.force_login(self.admin)

    def test_admin_can_deactivate_and_reactivate_a_user(self):
        url = reverse('admin_panel:user_management')
        self.client.post(url, {'user_id': self.student.id, 'action': 'deactivate'})
        self.student.refresh_from_db()
        self.assertFalse(self.student.is_active)
        self.client.post(url, {'user_id': self.student.id, 'action': 'activate'})
        self.student.refresh_from_db()
        self.assertTrue(self.student.is_active)

    def test_admin_cannot_deactivate_self(self):
        self.client.post(reverse('admin_panel:user_management'), {'user_id': self.admin.id, 'action': 'deactivate'})
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_deactivated_user_cannot_log_in(self):
        self.student.is_active = False
        self.student.save()
        c = self.client_class()
        r = c.post(reverse('login'), {'username': 'stu@shc.edu', 'password': 'pw-Test-12345', 'role': 'student'})
        self.assertEqual(r.status_code, 200)
        self.assertNotIn('_auth_user_id', c.session)
