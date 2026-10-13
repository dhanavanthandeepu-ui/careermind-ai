from django.urls import path
from . import views_admin as v
from careerpath.admin_views import career_requirements

urlpatterns = [
    path('', v.dashboard, name='dashboard'),
    path('students/', v.students, name='students'),
    path('staff/', v.staff, name='staff'),
    path('alumni/', v.alumni, name='alumni'),
    path('users/', v.user_management, name='user_management'),
    path('opportunities/', v.opportunities, name='opportunities'),
    path('courses/', v.courses, name='courses'),
    path('career-requirements/', career_requirements, name='career_requirements'),
    path('mentorship/', v.mentorship, name='mentorship'),
    path('events/', v.events, name='events'),
    path('workshops/', v.workshops, name='workshops'),
    path('applications/', v.applications, name='applications'),
    path('announcements/', v.announcements, name='announcements'),
    path('learning-resources/', v.learning_resources, name='learning_resources'),
    path('reports/', v.reports, name='reports'),
    path('notifications/', v.notifications, name='notifications'),
    path('settings/', v.settings_view, name='settings'),
]
