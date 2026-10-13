"""Workshop / session management shared by Staff and Alumni.
Staff and Alumni each get their own URL set (and sidebar) but use the same
logic here. Ownership is enforced on every object lookup."""
from django.contrib import messages
from django.db.models import Count
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_noop as _n

from core.models import Profile

from . import notifications as notes
from .forms_career import ALUMNI_EVENT_TYPES, STAFF_EVENT_TYPES, WorkshopForm
from .models import CareerEvent

CONFIG = {
    'staff': dict(types=STAFF_EVENT_TYPES, base='staff/base_staff.html', label='Workshops',
                  sections=['all', 'draft', 'pending', 'published', 'upcoming', 'completed']),
    'alumni': dict(types=ALUMNI_EVENT_TYPES, base='alumni/base_alumni.html', label='Sessions & Workshops',
                   sections=['all', 'draft', 'pending', 'published', 'rejected', 'upcoming', 'completed']),
}
SECTION_LABELS = dict(all='All', draft='Draft', pending='Pending Approval', published='Published',
                      rejected='Rejected', upcoming='Upcoming', completed='Completed')


def _own(request, pk):
    return get_object_or_404(CareerEvent, pk=pk, created_by=request.user)


def _section_filter(qs, section, today):
    if section == 'draft':
        return qs.filter(status='draft')
    if section == 'pending':
        return qs.filter(status='pending')
    if section == 'published':
        return qs.filter(status='published')
    if section == 'rejected':
        return qs.filter(status='rejected')
    if section == 'upcoming':
        return qs.filter(status='published', event_date__gte=today)
    if section == 'completed':
        return qs.filter(status='published', event_date__lt=today)
    return qs


def my_workshops(request, role):
    cfg = CONFIG[role]
    today = timezone.localdate()
    base = CareerEvent.objects.filter(created_by=request.user).annotate(reg_count=Count('registrations'))
    section = request.GET.get('section', 'all')
    if section not in cfg['sections']:
        section = 'all'
    counts = [(s, SECTION_LABELS[s], _section_filter(base, s, today).count()) for s in cfg['sections']]
    profile = Profile.objects.get_or_create(user=request.user)[0]
    return render(request, 'workshops/my_workshops.html', dict(
        base_template=cfg['base'], ns=role, profile=profile, active='workshops', heading=cfg['label'],
        events=_section_filter(base, section, today).order_by('-event_date'), section=section, counts=counts,
        today=today))


def workshop_form(request, role, pk=None):
    cfg = CONFIG[role]
    event = _own(request, pk) if pk else None
    if event and event.status not in ('draft', 'rejected'):
        messages.error(request, "Only drafts and rejected sessions can be edited.")
        return redirect(f'{role}:workshops')
    form = WorkshopForm(request.POST or None, request.FILES or None, instance=event, allowed_types=cfg['types'])
    if request.method == 'POST' and form.is_valid():
        ev = form.save(commit=False)
        if ev.event_type not in cfg['types']:       # never trust the posted type
            form.add_error('event_type', 'Choose a valid session type.')
        else:
            submit = request.POST.get('action') == 'submit'
            ev.created_by = request.user
            ev.organizer = request.user.get_full_name() or request.user.username
            ev.status = 'pending' if submit else 'draft'
            if submit:
                ev.review_note = ''
            ev.save()
            if submit:
                notes.notify_admins_pending(ev, 'Workshop')
                messages.success(request, "Submitted for admin approval. Students are notified once it is published.")
            else:
                messages.success(request, "Draft saved.")
            return redirect(f'{role}:workshops')
    profile = Profile.objects.get_or_create(user=request.user)[0]
    return render(request, 'workshops/form.html', dict(
        base_template=cfg['base'], ns=role, profile=profile, active='workshops', form=form, event=event))


def workshop_action(request, role, pk):
    """POST-only: submit / cancel / delete on the owner's own session."""
    event = _own(request, pk)
    action = request.POST.get('action')
    if action == 'submit' and event.status in ('draft', 'rejected'):
        event.status, event.review_note = 'pending', ''
        event.save(update_fields=['status', 'review_note'])
        notes.notify_admins_pending(event, 'Workshop')
        messages.success(request, "Submitted for admin approval.")
    elif action == 'delete' and event.status in ('draft', 'rejected'):
        event.delete()
        messages.success(request, "Session deleted.")
    elif action == 'cancel' and event.status == 'published':
        event.status = 'cancelled'
        event.save(update_fields=['status'])
        notes.notify(
            [r.student for r in event.registrations.select_related('student')],
            _n("Session cancelled"), _n("%(title)s on %(date)s has been cancelled."),
            event.notification_type, event, reverse('student:workshop_detail', args=[event.pk]),
            params={'title': event.title, 'date': event.event_date.isoformat()})
        messages.success(request, "Session cancelled and registered students notified.")
    else:
        messages.error(request, "That action isn't available for this session.")
    return redirect(f'{role}:workshops')


def workshop_registrations(request, role, pk):
    event = get_object_or_404(CareerEvent, pk=pk)
    allowed = event.created_by_id == request.user.pk or (role == 'staff' and event.status == 'published')
    if not allowed:
        raise Http404("Not found.")
    regs = event.registrations.select_related('student', 'student__profile__student_detail')
    profile = Profile.objects.get_or_create(user=request.user)[0]
    return render(request, 'workshops/registrations.html', dict(
        base_template=CONFIG[role]['base'], ns=role, profile=profile, active='workshops', event=event, regs=regs))
