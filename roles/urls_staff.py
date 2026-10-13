from django.urls import path
from . import views_staff as v

urlpatterns = [
    path('', v.dashboard, name='dashboard'),
    path('students/', v.students, name='students'),
    path('students/<int:user_id>/', v.student_profile, name='student_profile'),
    path('progress/', v.student_progress, name='student_progress'),
    path('resume-review/', v.resume_review, name='resume_review'),
    path('skill-analysis/', v.skill_analysis, name='skill_analysis'),
    path('career-guidance/', v.career_guidance, name='career_guidance'),
    path('opportunities/', v.opportunities, name='opportunities'),
    path('events/', v.events, name='events'),
    path('workshops/', v.workshops, name='workshops'),
    path('workshops/new/', v.workshop_new, name='workshop_new'),
    path('workshops/<int:pk>/edit/', v.workshop_edit, name='workshop_edit'),
    path('workshops/<int:pk>/action/', v.workshop_action, name='workshop_action'),
    path('workshops/<int:pk>/registrations/', v.workshop_registrations, name='workshop_registrations'),
    path('reports/', v.reports, name='reports'),
    path('profile/', v.staff_profile, name='profile'),
]
