from django.urls import path

from . import views

app_name = 'careerpath'

urlpatterns = [
    path('goal/', views.set_career_goal, name='set_goal'),
    path('roadmap/', views.roadmap_page, name='roadmap'),
    path('roadmap/recalculate/', views.recalculate_roadmap, name='recalculate_roadmap'),
    path('roadmap/milestone/<int:milestone_id>/toggle/', views.toggle_milestone, name='toggle_milestone'),
]
