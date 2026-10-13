from django.urls import path
from . import views_alumni as v

urlpatterns = [
    path('', v.dashboard, name='dashboard'),
    path('profile/', v.profile_view, name='profile'),
    path('career-journey/', v.career_journey, name='career_journey'),
    path('skills/', v.skills, name='skills'),
    path('mentorship/', v.mentorship, name='mentorship'),
    path('students/', v.students, name='students'),
    path('opportunities/', v.opportunities, name='opportunities'),
    path('opportunities/new/', v.opportunity_form, name='opportunity_new'),
    path('opportunities/<int:pk>/edit/', v.opportunity_form, name='opportunity_edit'),
    path('opportunities/<int:pk>/action/', v.opportunity_action, name='opportunity_action'),
    path('opportunities/<int:pk>/applicants/', v.opportunity_applicants, name='opportunity_applicants'),
    path('workshops/', v.workshops, name='workshops'),
    path('workshops/new/', v.workshop_new, name='workshop_new'),
    path('workshops/<int:pk>/edit/', v.workshop_edit, name='workshop_edit'),
    path('workshops/<int:pk>/action/', v.workshop_action, name='workshop_action'),
    path('workshops/<int:pk>/registrations/', v.workshop_registrations, name='workshop_registrations'),
    path('referrals/', v.referrals, name='referrals'),
    path('events/', v.events, name='events'),
    path('messages/', v.messages_view, name='messages'),
    path('settings/', v.settings_view, name='settings'),
]
