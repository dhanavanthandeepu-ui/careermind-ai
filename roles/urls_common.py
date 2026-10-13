from django.urls import path

from . import views_notifications as v

urlpatterns = [
    path('notifications/', v.notification_list, name='notifications'),
    path('notifications/read-all/', v.notification_mark_all_read, name='notifications_read_all'),
    path('notifications/<int:pk>/open/', v.notification_open, name='notification_open'),
    path('notifications/<int:pk>/read/', v.notification_mark_read, name='notification_mark_read'),
]
