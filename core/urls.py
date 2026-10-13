from django.urls import path
from . import views
from roles.views import faculty_signup

urlpatterns = [
    path('', views.landing, name='landing'),
    path('signup/', views.SignUpView.as_view(), name='signup'),
    path('faculty-signup/', faculty_signup, name='faculty_signup'),
    path('login/', views.PortalLoginView.as_view(), name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('skill-analysis/', views.skill_analysis, name='skill_analysis'),
    path('resume-analyzer/', views.resume_analyzer, name='resume_analyzer'),
    path('resume-analyzer/feedback-pdf/', views.feedback_pdf, name='feedback_pdf'),
    path('learning-roadmap/', views.learning_roadmap, name='learning_roadmap'),
    path('learning-roadmap/progress/<int:resource_id>/', views.api_learning_progress, name='api_learning_progress'),
    path('chatbot/', views.ai_chatbot, name='ai_chatbot'),
    path('chatbot/reply/', views.chatbot_reply, name='chatbot_reply'),
    path('api/test/', views.api_test, name='api_test'),
    path('api/resume/upload/', views.api_resume_upload, name='api_resume_upload'),
    path('api/resume/request-review/', views.api_request_resume_review, name='api_request_resume_review'),
]
