from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('i18n/', include('django.conf.urls.i18n')),
    path('', include('core.urls')),
    path('career/', include('careerpath.urls')),
    path('', include('roles.urls_common')),
    path('student/', include(('roles.urls_student', 'student'), namespace='student')),
    path('staff/', include(('roles.urls_staff', 'staff'), namespace='staff')),
    path('alumni/', include(('roles.urls_alumni', 'alumni'), namespace='alumni')),
    path('admin-panel/', include(('roles.urls_admin', 'admin_panel'), namespace='admin_panel')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
