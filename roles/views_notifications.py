"""Notification centre shared by all four roles. A user can only ever see or
change their own notifications (every query is scoped to request.user)."""
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from core.models import Profile

from . import notifications as notes
from .decorators import _effective_role
from .models import Notification

FILTERS = [
    ('all', _('All'), None),
    ('unread', _('Unread'), None),
    ('workshops', _('Workshops'), ['workshop', 'seminar']),
    ('jobs', _('Jobs'), ['job']),
    ('internships', _('Internships'), ['internship']),
    ('mentorship', _('Mentorship'), ['mentorship']),
    ('applications', _('Applications'), ['application']),
    ('announcements', _('Announcements'), ['announcement']),
    ('updates', _('Learning & Career'), ['learning_resource', 'career_update']),
]
BASE_TEMPLATES = {
    'student': 'core/base.html',
    'staff': 'staff/base_staff.html',
    'alumni': 'alumni/base_alumni.html',
    'admin': 'admin_panel/base_admin.html',
}


def render_notification_page(request, active='notifications'):
    profile, _created = Profile.objects.get_or_create(user=request.user)
    role = _effective_role(request.user, profile)
    current = request.GET.get('filter', 'all')
    qs = Notification.objects.filter(recipient=request.user)
    types = None
    for key, _label, t in FILTERS:
        if key == current:
            types = t
    if current == 'unread':
        qs = qs.filter(is_read=False)
    elif types:
        qs = qs.filter(notification_type__in=types)
    else:
        current = 'all'
    page = Paginator(qs.order_by('-created_at'), 15).get_page(request.GET.get('page'))
    return render(request, 'notifications/list.html', dict(
        base_template=BASE_TEMPLATES.get(role, 'core/base.html'), profile=profile, active=active,
        page=page, current=current, filters=[(k, l) for k, l, _t in FILTERS],
        unread_total=notes.unread_count(request.user), qs_params=f'filter={current}'))


@login_required
def notification_list(request):
    return render_notification_page(request)


@login_required
def notification_open(request, pk):
    """Opening a notification marks it read, then goes to the related page."""
    n = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notes.mark_read(n)
    target = n.link
    if target and url_has_allowed_host_and_scheme(target, allowed_hosts=None) and target.startswith('/'):
        return redirect(target)
    return redirect('notifications')


@login_required
@require_POST
def notification_mark_read(request, pk):
    n = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notes.mark_read(n)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'ok': True, 'unread': notes.unread_count(request.user)})
    return redirect(request.POST.get('next') if (request.POST.get('next') or '').startswith('/') else 'notifications')


@login_required
@require_POST
def notification_mark_all_read(request):
    notes.mark_all_read(request.user)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'ok': True, 'unread': 0})
    return redirect(request.POST.get('next') if (request.POST.get('next') or '').startswith('/') else 'notifications')
