import datetime
import random

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Profile
from roles.models import (
    StaffDetail, AlumniDetail, AdminDetail, Opportunity, CareerEvent, Course,
    MentorshipRequest, GuidanceRequest, ResumeReview, StudentActivity,
    Notification, Message, Referral,
)


class Command(BaseCommand):
    help = "Seed demo Staff / Alumni / Admin accounts and sample platform data for CareerMind AI."

    def handle(self, *args, **options):
        self.stdout.write("Seeding CareerMind demo data...")

        # ---- demo accounts (one per role, plus a couple more students) ----
        staff_user = self._get_or_create_user('staff.demo@shc.edu', 'Ritu', 'Menon', 'staff')
        alumni_user = self._get_or_create_user('alumni.demo@shc.edu', 'Arjun', 'Iyer', 'alumni')
        admin_user = self._get_or_create_user('admin.demo@shc.edu', 'Kavya', 'Nair', 'admin')

        extra_students = [
            ('priya.s@shc.edu', 'Priya', 'Sundaram'),
            ('rahul.k@shc.edu', 'Rahul', 'Krishnan'),
            ('meera.v@shc.edu', 'Meera', 'Venkatesh'),
        ]
        student_users = []
        for email, first, last in extra_students:
            u = self._get_or_create_user(email, first, last, 'student')
            student_users.append(u)

        staff_profile = Profile.objects.get(user=staff_user)
        StaffDetail.objects.get_or_create(profile=staff_profile, defaults=dict(
            department='Placement Cell', designation='Senior Career Counselor', students_assigned=Profile.objects.filter(role='student').count()))

        alumni_profile = Profile.objects.get(user=alumni_user)
        AlumniDetail.objects.get_or_create(profile=alumni_profile, defaults=dict(
            current_company='Google', designation='Senior Software Engineer',
            graduation_year=2019, experience_years=6, industry='Technology',
            bio='SHC AI/ML alum now building infra at Google. Happy to mentor on system design and interview prep.',
        ))

        admin_profile = Profile.objects.get(user=admin_user)
        AdminDetail.objects.get_or_create(profile=admin_profile, defaults=dict(designation='Platform Administrator'))

        # ---- opportunities ----
        if Opportunity.objects.count() == 0:
            Opportunity.objects.bulk_create([
                Opportunity(title="Software Engineer Intern", company="Google", kind="internship",
                            location="Bangalore (Remote)", pay="₹1,20,000/mo", status="open",
                            posted_by_alumni=alumni_user, deadline=timezone.now().date() + datetime.timedelta(days=20)),
                Opportunity(title="Data Analyst", company="Microsoft", kind="job", location="Hyderabad",
                            pay="₹18-24 LPA", status="open", deadline=timezone.now().date() + datetime.timedelta(days=30)),
                Opportunity(title="ML Engineer", company="Adobe", kind="job", location="Noida",
                            pay="₹20-26 LPA", status="pending", posted_by_alumni=alumni_user),
                Opportunity(title="Product Design Intern", company="Zoho", kind="internship", location="Chennai",
                            pay="₹35,000/mo", status="open"),
            ])

        # ---- career events ----
        if CareerEvent.objects.count() == 0:
            today = timezone.now().date()
            CareerEvent.objects.bulk_create([
                CareerEvent(title="Campus Placement Drive", description="On-campus drive with 12 recruiting companies.",
                            event_date=today + datetime.timedelta(days=10), location="Main Auditorium", organizer="Placement Cell"),
                CareerEvent(title="Alumni Mentorship Mixer", description="Meet alumni working across AI, cloud, and product roles.",
                            event_date=today + datetime.timedelta(days=18), location="Seminar Hall B", organizer="Alumni Relations"),
                CareerEvent(title="Resume & LinkedIn Workshop", description="Hands-on resume review and LinkedIn optimization session.",
                            event_date=today + datetime.timedelta(days=5), location="AI/ML Dept Lab", organizer="Career Services"),
            ])

        # ---- courses ----
        if Course.objects.count() == 0:
            Course.objects.bulk_create([
                Course(title="Applied Machine Learning", provider="CareerMind Learning", category="Technical", duration_weeks=6, enrolled_count=42),
                Course(title="System Design Fundamentals", provider="CareerMind Learning", category="Technical", duration_weeks=4, enrolled_count=35),
                Course(title="Interview Communication Skills", provider="CareerMind Learning", category="Soft Skills", duration_weeks=2, enrolled_count=58),
            ])

        # ---- student activity / mentorship / guidance / reviews / notifications ----
        all_students = list(User.objects.filter(profile__role='student'))
        for s in all_students:
            Profile.objects.get_or_create(user=s)
            profile = s.profile

            StudentActivity.objects.get_or_create(
                student=s, description="updated their resume",
                defaults=dict())
            GuidanceRequest.objects.get_or_create(
                student=s, topic="Interview preparation for product roles",
                defaults=dict(status='open'))
            ResumeReview.objects.get_or_create(
                student=s, defaults=dict(status='pending'))
            MentorshipRequest.objects.get_or_create(
                student=s, alumni=alumni_user, topic="Breaking into big tech",
                defaults=dict(status='pending'))
            Notification.objects.get_or_create(
                recipient=admin_user, message=f"{s.first_name} {s.last_name} signed up as a student",
                defaults=dict())

        if Message.objects.count() == 0 and all_students:
            Message.objects.create(sender=all_students[0], recipient=alumni_user,
                                    body="Hi! Would love your advice on breaking into ML roles.")

        if Referral.objects.count() == 0 and all_students:
            opp = Opportunity.objects.filter(posted_by_alumni=alumni_user).first()
            Referral.objects.create(alumni=alumni_user, student=all_students[0], opportunity=opp, status='in_review')

        self.stdout.write(self.style.SUCCESS(
            "Demo data seeded. Login with: staff.demo@shc.edu / alumni.demo@shc.edu / admin.demo@shc.edu (password: CareerMind@2026)"
        ))

    def _get_or_create_user(self, email, first, last, role):
        user, created = User.objects.get_or_create(
            username=email, defaults=dict(email=email, first_name=first, last_name=last))
        if created:
            user.set_password('CareerMind@2026')
            user.save()
        profile, _ = Profile.objects.get_or_create(user=user, defaults=dict(university_email=email, role=role))
        if profile.role != role:
            profile.role = role
            profile.save()
        return user
