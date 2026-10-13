from django.urls import path

from . import views_student as v

urlpatterns = [
    path('opportunities/', v.opportunities, name='opportunities'),
    path('opportunities/<int:pk>/', v.opportunity_detail, name='opportunity_detail'),
    path('opportunities/<int:pk>/apply/', v.opportunity_apply, name='opportunity_apply'),
    path('applications/', v.my_applications, name='my_applications'),
    path('mentors/', v.find_mentor, name='find_mentor'),
    path('mentors/<int:user_id>/', v.mentor_profile, name='mentor_profile'),
    path('mentors/<int:user_id>/request/', v.request_mentorship, name='request_mentorship'),
    path('my-mentorship/', v.my_mentorship, name='my_mentorship'),
    path('workshops/', v.workshops, name='workshops'),
    path('workshops/<int:pk>/', v.workshop_detail, name='workshop_detail'),
    path('workshops/<int:pk>/register/', v.workshop_register, name='workshop_register'),
]
