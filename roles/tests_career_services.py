"""End-to-end tests for the Student <-> Staff <-> Alumni <-> Admin career services."""
import datetime

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from careerpath.models import CareerDomain, CareerRole, Company, StudentCareerGoal
from core.models import Resume
from core.tests import make_user
from roles.models import (Application, CareerEvent, EventRegistration, MentorshipRequest,
                          Notification, Opportunity)


class Base(TestCase):
    def setUp(self):
        self.student = make_user('stu@shc.edu', 'student')
        self.student2 = make_user('stu2@shc.edu', 'student')
        self.alumni = make_user('alum@shc.edu', 'alumni')
        self.staff = make_user('staff@shc.edu', 'staff')
        self.admin = make_user('adm@shc.edu', 'admin')
        self.tomorrow = timezone.localdate() + datetime.timedelta(days=7)

    def as_(self, user):
        self.client.force_login(user)
        return self.client

    def published_job(self, **kw):
        data = dict(title='Data Analyst', company='ABC Technologies', kind='job', status='open',
                    posted_by_alumni=self.alumni, skills='Python, SQL')
        data.update(kw)
        return Opportunity.objects.create(**data)

    def workshop_data(self, **kw):
        data = dict(title='AI & ML Career Workshop', event_type='workshop', description='Intro',
                    event_date=self.tomorrow.isoformat(), event_time='10:00', location='Hall A', mode='offline',
                    action='submit')
        data.update(kw)
        return data


class JobFlowTests(Base):
    def test_1_alumni_job_to_admin_to_student_apply(self):
        self.as_(self.alumni).post(reverse('alumni:opportunity_new'), dict(
            title='Data Analyst', company='ABC Technologies', kind='job', employment_type='full_time',
            location='Chennai', skills='Python, SQL', action='submit'))
        opp = Opportunity.objects.get()
        self.assertEqual(opp.status, 'pending')
        # admin was told
        self.assertTrue(Notification.objects.filter(recipient=self.admin).exists())
        # hidden from students while pending
        self.assertEqual(self.as_(self.student).get(reverse('student:opportunity_detail', args=[opp.pk])).status_code, 404)

        self.as_(self.admin).post(reverse('admin_panel:opportunities'), {'opp_id': opp.pk, 'action': 'approve'})
        opp.refresh_from_db()
        self.assertEqual(opp.status, 'open')
        n = Notification.objects.get(recipient=self.student, notification_type='job')
        self.assertIn('Data Analyst', n.message)

        c = self.as_(self.student)
        self.assertContains(c.get(reverse('student:opportunities')), 'Data Analyst')
        self.assertContains(c.get(reverse('student:opportunity_detail', args=[opp.pk])), 'Apply Now')
        r = c.post(reverse('student:opportunity_apply', args=[opp.pk]), {'cover_note': 'I am keen.'})
        self.assertRedirects(r, reverse('student:my_applications'))
        self.assertEqual(Application.objects.filter(student=self.student, opportunity=opp, status='applied').count(), 1)
        self.assertContains(c.get(reverse('student:my_applications')), 'Data Analyst')

    def test_duplicate_application_blocked(self):
        opp = self.published_job()
        c = self.as_(self.student)
        c.post(reverse('student:opportunity_apply', args=[opp.pk]), {'cover_note': 'one'})
        c.post(reverse('student:opportunity_apply', args=[opp.pk]), {'cover_note': 'two'})
        self.assertEqual(Application.objects.count(), 1)
        self.assertContains(c.get(reverse('student:opportunities')), 'Applied')

    def test_cannot_apply_to_unpublished_or_expired(self):
        pending = self.published_job(status='pending')
        old = self.published_job(title='Old', deadline=timezone.localdate() - datetime.timedelta(days=1))
        c = self.as_(self.student)
        self.assertEqual(c.post(reverse('student:opportunity_apply', args=[pending.pk]), {'cover_note': 'x'}).status_code, 404)
        c.post(reverse('student:opportunity_apply', args=[old.pk]), {'cover_note': 'x'})
        self.assertEqual(Application.objects.count(), 0)

    def test_rejected_post_hidden_and_alumni_sees_status(self):
        self.as_(self.alumni).post(reverse('alumni:opportunity_new'), dict(
            title='Weak Post', company='X', kind='job', employment_type='full_time', location='Remote', action='submit'))
        opp = Opportunity.objects.get()
        self.as_(self.admin).post(reverse('admin_panel:opportunities'),
                                  {'opp_id': opp.pk, 'action': 'reject', 'review_note': 'Too vague'})
        opp.refresh_from_db()
        self.assertEqual((opp.status, opp.review_note), ('rejected', 'Too vague'))
        self.assertFalse(Notification.objects.filter(recipient=self.student).exists())
        self.assertContains(self.as_(self.alumni).get(reverse('alumni:opportunities')), 'Too vague')
        self.assertNotContains(self.as_(self.student).get(reverse('student:opportunities')), 'Weak Post')

    def test_2_internship_notification_type(self):
        self.as_(self.alumni).post(reverse('alumni:opportunity_new'), dict(
            title='AI/ML Internship', company='X', kind='internship', employment_type='internship',
            location='Remote', action='submit'))
        opp = Opportunity.objects.get()
        self.as_(self.admin).post(reverse('admin_panel:opportunities'), {'opp_id': opp.pk, 'action': 'approve'})
        n = Notification.objects.get(recipient=self.student)
        self.assertEqual((n.notification_type, n.title), ('internship', 'New Internship Available'))
        # approving twice must not notify twice
        self.as_(self.admin).post(reverse('admin_panel:opportunities'), {'opp_id': opp.pk, 'action': 'approve'})
        self.assertEqual(Notification.objects.filter(recipient=self.student).count(), 1)

    def test_6_admin_status_change_notifies_student(self):
        opp = self.published_job()
        app = Application.objects.create(student=self.student, opportunity=opp, cover_note='hi')
        self.as_(self.admin).post(reverse('admin_panel:applications'), {'application_id': app.pk, 'status': 'shortlisted'})
        app.refresh_from_db()
        self.assertEqual(app.status, 'shortlisted')
        n = Notification.objects.get(recipient=self.student, notification_type='application')
        self.assertIn('shortlisted', n.message)
        self.assertIn('Data Analyst', n.message)
        # same status again -> no duplicate notification
        self.as_(self.admin).post(reverse('admin_panel:applications'), {'application_id': app.pk, 'status': 'shortlisted'})
        self.assertEqual(Notification.objects.filter(recipient=self.student).count(), 1)
        # invalid status ignored
        self.as_(self.admin).post(reverse('admin_panel:applications'), {'application_id': app.pk, 'status': 'hacked'})
        app.refresh_from_db()
        self.assertEqual(app.status, 'shortlisted')

    def test_domain_targeting_limits_job_notifications(self):
        dom = CareerDomain.objects.create(name='Data')
        other = CareerDomain.objects.create(name='Web')
        role = CareerRole.objects.create(domain=dom, name='Data Analyst')
        co = Company.objects.create(name='Co')
        StudentCareerGoal.objects.create(profile=self.student.profile, domain=dom, role=role, company=co)
        opp = self.published_job(status='pending', target_domain=dom, target_role=role)
        self.as_(self.admin).post(reverse('admin_panel:opportunities'), {'opp_id': opp.pk, 'action': 'approve'})
        self.assertTrue(Notification.objects.filter(recipient=self.student).exists())
        self.assertFalse(Notification.objects.filter(recipient=self.student2).exists())
        self.assertNotEqual(other.pk, dom.pk)

    def test_match_percentage_only_with_real_data(self):
        self.published_job()
        html = self.as_(self.student).get(reverse('student:opportunities')).content.decode()
        self.assertNotIn('% match', html)          # no resume -> no score
        Resume.objects.create(profile=self.student.profile, file='r.pdf', skills=['Python'])
        html = self.client.get(reverse('student:opportunities')).content.decode()
        self.assertIn('50% match', html)


class MentorshipTests(Base):
    def test_3_request_accept_connected(self):
        c = self.as_(self.student)
        self.assertContains(c.get(reverse('student:find_mentor')), 'Alum')
        c.post(reverse('student:request_mentorship', args=[self.alumni.pk]),
               {'topic': 'Break into ML', 'message': 'Please guide me.'})
        mr = MentorshipRequest.objects.get()
        self.assertEqual(mr.status, 'pending')
        self.assertTrue(Notification.objects.filter(recipient=self.alumni, notification_type='mentorship').exists())

        self.as_(self.alumni).post(reverse('alumni:mentorship'), {'request_id': mr.pk, 'action': 'accept'})
        mr.refresh_from_db()
        self.assertEqual(mr.status, 'accepted')
        n = Notification.objects.get(recipient=self.student, notification_type='mentorship')
        self.assertIn('accepted', n.message)
        self.assertContains(self.as_(self.student).get(reverse('student:my_mentorship')), 'Connected')
        self.assertContains(self.as_(self.alumni).get(reverse('alumni:mentorship')), 'Connected Students (1)')

    def test_duplicate_pending_blocked_and_reject_notifies(self):
        c = self.as_(self.student)
        url = reverse('student:request_mentorship', args=[self.alumni.pk])
        c.post(url, {'topic': 'A', 'message': 'm'})
        c.post(url, {'topic': 'B', 'message': 'm'})
        self.assertEqual(MentorshipRequest.objects.count(), 1)
        mr = MentorshipRequest.objects.get()
        self.as_(self.alumni).post(reverse('alumni:mentorship'), {'request_id': mr.pk, 'action': 'reject'})
        mr.refresh_from_db()
        self.assertEqual(mr.status, 'declined')
        self.assertTrue(Notification.objects.filter(recipient=self.student, title__icontains='rejected').exists())
        # an answered request cannot be flipped
        self.as_(self.alumni).post(reverse('alumni:mentorship'), {'request_id': mr.pk, 'action': 'accept'})
        mr.refresh_from_db()
        self.assertEqual(mr.status, 'declined')

    def test_other_alumni_cannot_answer(self):
        other = make_user('alum2@shc.edu', 'alumni')
        mr = MentorshipRequest.objects.create(student=self.student, alumni=self.alumni, topic='t')
        r = self.as_(other).post(reverse('alumni:mentorship'), {'request_id': mr.pk, 'action': 'accept'})
        self.assertEqual(r.status_code, 404)

    def test_unwilling_alumni_not_listed(self):
        d = self.alumni.profile.alumni_detail
        d.willing_to_mentor = False
        d.save()
        self.assertEqual(self.as_(self.student).get(reverse('student:mentor_profile', args=[self.alumni.pk])).status_code, 404)


class WorkshopTests(Base):
    def test_4_staff_workshop_to_registration(self):
        self.as_(self.staff).post(reverse('staff:workshop_new'), self.workshop_data())
        ev = CareerEvent.objects.get()
        self.assertEqual((ev.status, ev.created_by), ('pending', self.staff))
        self.assertEqual(self.as_(self.student).get(reverse('student:workshop_detail', args=[ev.pk])).status_code, 404)

        self.as_(self.admin).post(reverse('admin_panel:workshops'), {'event_id': ev.pk, 'action': 'approve'})
        ev.refresh_from_db()
        self.assertEqual(ev.status, 'published')
        n = Notification.objects.get(recipient=self.student)
        self.assertEqual(n.notification_type, 'workshop')
        self.assertEqual(n.link, reverse('student:workshop_detail', args=[ev.pk]))
        self.assertTrue(Notification.objects.filter(recipient=self.staff, title__icontains='approved').exists())

        c = self.as_(self.student)
        self.assertContains(c.get(n.link), 'Register Now')
        c.post(reverse('student:workshop_register', args=[ev.pk]))
        c.post(reverse('student:workshop_register', args=[ev.pk]))     # duplicate
        self.assertEqual(EventRegistration.objects.count(), 1)
        self.assertContains(c.get(n.link), 'Registered')

    def test_5_alumni_industry_session(self):
        self.as_(self.alumni).post(reverse('alumni:workshop_new'), self.workshop_data(
            title='Industry Talk', event_type='industry_talk'))
        ev = CareerEvent.objects.get()
        self.as_(self.admin).post(reverse('admin_panel:workshops'), {'event_id': ev.pk, 'action': 'approve'})
        self.assertTrue(Notification.objects.filter(recipient=self.student, message__contains='Industry Talk').exists())
        self.assertContains(self.as_(self.student).get(reverse('student:workshop_detail', args=[ev.pk])), 'Industry Talk')

    def test_role_limited_session_types(self):
        r = self.as_(self.staff).post(reverse('staff:workshop_new'), self.workshop_data(event_type='industry_talk'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(CareerEvent.objects.count(), 0)

    def test_registration_closed_after_deadline(self):
        ev = CareerEvent.objects.create(
            title='Late', event_date=self.tomorrow, status='published', created_by=self.staff,
            registration_deadline=timezone.localdate() - datetime.timedelta(days=1))
        c = self.as_(self.student)
        self.assertContains(c.get(reverse('student:workshop_detail', args=[ev.pk])), 'Registration Closed')
        c.post(reverse('student:workshop_register', args=[ev.pk]))
        self.assertEqual(EventRegistration.objects.count(), 0)

    def test_online_requires_link(self):
        self.as_(self.staff).post(reverse('staff:workshop_new'), self.workshop_data(mode='online'))
        self.assertEqual(CareerEvent.objects.count(), 0)

    def test_staff_cannot_edit_others_session(self):
        ev = CareerEvent.objects.create(title='Mine', event_date=self.tomorrow, status='draft', created_by=self.alumni)
        self.assertEqual(self.as_(self.staff).get(reverse('staff:workshop_edit', args=[ev.pk])).status_code, 404)


class NotificationTests(Base):
    def make(self, user, **kw):
        data = dict(recipient=user, title='T', message='M', notification_type='job', link='/dashboard/')
        data.update(kw)
        return Notification.objects.create(**data)

    def test_7_open_marks_read_and_count_drops(self):
        n1, n2 = self.make(self.student), self.make(self.student)
        c = self.as_(self.student)
        self.assertEqual(c.get(reverse('dashboard')).context['nav_unread_count'], 2)
        r = c.get(reverse('notification_open', args=[n1.pk]))
        self.assertRedirects(r, '/dashboard/', fetch_redirect_response=False)
        n1.refresh_from_db()
        self.assertTrue(n1.is_read)
        self.assertEqual(c.get(reverse('dashboard')).context['nav_unread_count'], 1)
        c.post(reverse('notifications_read_all'))
        n2.refresh_from_db()
        self.assertTrue(n2.is_read)

    def test_cannot_touch_other_users_notifications(self):
        n = self.make(self.student2)
        c = self.as_(self.student)
        self.assertEqual(c.get(reverse('notification_open', args=[n.pk])).status_code, 404)
        self.assertEqual(c.post(reverse('notification_mark_read', args=[n.pk])).status_code, 404)
        c.post(reverse('notifications_read_all'))
        n.refresh_from_db()
        self.assertFalse(n.is_read)

    def test_filters_and_open_redirect_safety(self):
        self.make(self.student, notification_type='workshop', title='W')
        self.make(self.student, notification_type='job', title='J', is_read=True)
        bad = self.make(self.student, link='https://evil.example/')
        c = self.as_(self.student)
        titles = [n.title for n in c.get(reverse('notifications') + '?filter=workshops').context['page']]
        self.assertEqual(titles, ['W'])
        self.assertEqual(len(c.get(reverse('notifications') + '?filter=unread').context['page']), 2)
        r = c.get(reverse('notification_open', args=[bad.pk]))
        self.assertRedirects(r, reverse('notifications'), fetch_redirect_response=False)

    def test_every_role_can_open_notification_page(self):
        for u in (self.student, self.staff, self.alumni, self.admin):
            self.assertEqual(self.as_(u).get(reverse('notifications')).status_code, 200)

    def test_announcement_reaches_audience_only(self):
        self.as_(self.admin).post(reverse('admin_panel:announcements'),
                                  {'title': 'Placement Drive', 'message': 'Next week', 'audience': 'student'})
        self.assertTrue(Notification.objects.filter(recipient=self.student, notification_type='announcement').exists())
        self.assertFalse(Notification.objects.filter(recipient=self.alumni).exists())


class RoleSecurityTests(Base):
    def test_student_pages_closed_to_other_roles(self):
        for u in (self.alumni, self.staff, self.admin):
            c = self.as_(u)
            for name in ('student:opportunities', 'student:my_applications', 'student:find_mentor', 'student:workshops'):
                self.assertEqual(c.get(reverse(name)).status_code, 302, name)   # redirected to own portal
        opp = self.published_job()
        self.as_(self.alumni).post(reverse('student:opportunity_apply', args=[opp.pk]), {'cover_note': 'x'})
        self.assertEqual(Application.objects.count(), 0)

    def test_only_admin_can_review(self):
        opp = self.published_job(status='pending')
        ev = CareerEvent.objects.create(title='E', event_date=self.tomorrow, status='pending', created_by=self.staff)
        app = Application.objects.create(student=self.student, opportunity=opp)
        for u in (self.student, self.alumni, self.staff):
            c = self.as_(u)
            self.assertEqual(c.post(reverse('admin_panel:workshops'), {'event_id': ev.pk, 'action': 'approve'}).status_code, 403)
            self.assertEqual(c.post(reverse('admin_panel:applications'), {'application_id': app.pk, 'status': 'selected'}).status_code, 403)
            self.assertEqual(c.post(reverse('admin_panel:announcements'), {'title': 'x', 'message': 'y'}).status_code, 403)
        ev.refresh_from_db()
        self.assertEqual(ev.status, 'pending')

    def test_alumni_cannot_publish_directly_or_edit_others(self):
        self.as_(self.alumni).post(reverse('alumni:opportunity_new'), dict(
            title='Sneaky', company='X', kind='job', employment_type='full_time', location='R', action='submit', status='open'))
        self.assertEqual(Opportunity.objects.get().status, 'pending')
        other = make_user('alum2@shc.edu', 'alumni')
        opp = Opportunity.objects.get()
        self.assertEqual(self.as_(other).post(reverse('alumni:opportunity_action', args=[opp.pk]), {'action': 'delete'}).status_code, 404)

    def test_mutations_are_post_only(self):
        ev = CareerEvent.objects.create(title='E', event_date=self.tomorrow, status='published', created_by=self.staff)
        self.assertEqual(self.as_(self.student).get(reverse('student:workshop_register', args=[ev.pk])).status_code, 405)
        self.assertEqual(self.as_(self.student).get(reverse('student:request_mentorship', args=[self.alumni.pk])).status_code, 405)

    def test_existing_events_remain_visible_after_migration_defaults(self):
        ev = CareerEvent.objects.create(title='Legacy Fair', event_date=self.tomorrow)   # default status
        self.assertEqual(ev.status, 'published')
        self.assertContains(self.as_(self.student).get(reverse('student:workshops')), 'Legacy Fair')


class MultilingualTests(Base):
    LANGS = {'hi': 'मार्गदर्शक खोजें', 'ta': 'வழிகாட்டியைத் தேடு', 'te': 'మెంటర్‌ను కనుగొనండి',
             'kn': 'ಮಾರ್ಗದರ್ಶಕರನ್ನು ಹುಡುಕಿ', 'ml': 'മെന്ററെ കണ്ടെത്തുക'}

    def test_student_pages_render_in_every_language(self):
        from django.conf import settings
        self.published_job()
        c = self.as_(self.student)
        for code, find_mentor_label in self.LANGS.items():
            c.cookies[settings.LANGUAGE_COOKIE_NAME] = code
            html = c.get(reverse('student:find_mentor')).content.decode()
            self.assertIn(find_mentor_label, html, code)
            for name in ('student:opportunities', 'student:my_applications', 'student:my_mentorship',
                         'student:workshops', 'notifications'):
                self.assertEqual(c.get(reverse(name)).status_code, 200, (code, name))

    def test_notification_text_follows_the_readers_language(self):
        from django.utils import translation
        self.published_job(status='pending')
        opp = Opportunity.objects.get()
        self.as_(self.admin).post(reverse('admin_panel:opportunities'), {'opp_id': opp.pk, 'action': 'approve'})
        n = Notification.objects.get(recipient=self.student)
        with translation.override('en'):
            self.assertIn('has been posted', n.display_message)
        with translation.override('hi'):
            self.assertIn('पोस्ट', n.display_message)
            self.assertIn('Data Analyst', n.display_message)      # dynamic values are kept
            self.assertNotEqual(n.display_title, n.title)

    def test_legacy_notification_without_key_still_displays(self):
        n = Notification.objects.create(recipient=self.student, message='Plain old message')
        self.assertEqual(n.display_message, 'Plain old message')
