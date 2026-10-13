import datetime

from django.contrib.auth.models import User
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.models import LearningResource, Profile
from . import notifications as notes
from .decorators import role_required
from .forms_career import AnnouncementForm, LearningResourceForm, OpportunityForm
from .models import (
    AdminDetail, StaffDetail, AlumniDetail, Opportunity, CareerEvent,
    Course, MentorshipRequest, Notification, Application, EventRegistration, Announcement,
)
from .views_notifications import render_notification_page


def _qs(request):
    params = request.GET.copy()
    params.pop('page', None)
    return params.urlencode()


def _admin_detail(user):
    profile, _ = Profile.objects.get_or_create(user=user)
    detail, _ = AdminDetail.objects.get_or_create(profile=profile)
    return profile, detail


@role_required('admin')
def dashboard(request):
    profile, detail = _admin_detail(request.user)
    total_students = Profile.objects.filter(role='student').count()
    total_staff = Profile.objects.filter(role='staff').count()
    total_alumni = Profile.objects.filter(role='alumni').count()
    active_users = User.objects.filter(is_active=True).count()
    jobs = Opportunity.objects.filter(kind='job').count()
    internships = Opportunity.objects.filter(kind='internship').count()
    pending_opps = Opportunity.objects.filter(status='pending').count()
    pending_events = CareerEvent.objects.filter(status='pending').count()
    pending_approvals = pending_opps + pending_events
    today = timezone.localdate()
    events_count = CareerEvent.objects.filter(status='published', event_date__gte=today).count()
    published_opps = Opportunity.objects.filter(status='open').count()
    mentorship_total = MentorshipRequest.objects.count()
    applications_total = Application.objects.count()

    students_qs = Profile.objects.filter(role='student')
    avg_placement = round(sum(s.readiness_score for s in students_qs) / total_students) if total_students else 0

    recent_activity = [
        f"{u.first_name} {u.last_name} joined as {p.role}"
        for p, u in [(p, p.user) for p in Profile.objects.select_related('user').order_by('-id')[:6]]
    ]

    context = dict(
        profile=profile, detail=detail, active='dashboard',
        total_students=total_students, total_staff=total_staff, total_alumni=total_alumni,
        active_users=active_users, jobs=jobs, internships=internships,
        pending_approvals=pending_approvals, events_count=events_count,
        pending_opps=pending_opps, pending_events=pending_events, published_opps=published_opps,
        mentorship_total=mentorship_total, applications_total=applications_total,
        avg_placement=avg_placement, recent_activity=recent_activity,
        chart_labels=["Students", "Staff", "Alumni"],
        chart_values=[total_students, total_staff, total_alumni],
    )
    return render(request, 'admin_panel/dashboard.html', context)


@role_required('admin')
def students(request):
    profile, detail = _admin_detail(request.user)
    student_list = Profile.objects.filter(role='student').select_related('user')
    context = dict(profile=profile, active='students', student_list=student_list)
    return render(request, 'admin_panel/students.html', context)


@role_required('admin')
def staff(request):
    profile, detail = _admin_detail(request.user)
    staff_list = Profile.objects.filter(role='staff').select_related('user')
    context = dict(profile=profile, active='staff', staff_list=staff_list)
    return render(request, 'admin_panel/staff.html', context)


@role_required('admin')
def alumni(request):
    profile, detail = _admin_detail(request.user)
    alumni_list = Profile.objects.filter(role='alumni').select_related('user')
    context = dict(profile=profile, active='alumni', alumni_list=alumni_list)
    return render(request, 'admin_panel/alumni.html', context)


@role_required('admin')
def user_management(request):
    profile, detail = _admin_detail(request.user)
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        action = request.POST.get('action')
        target = get_object_or_404(User, id=user_id)
        target_profile, _ = Profile.objects.get_or_create(user=target)
        if action == 'deactivate' and target.pk == request.user.pk:
            messages.error(request, "You can't deactivate your own account.")
            return redirect('admin_panel:user_management')
        if action == 'deactivate':
            target.is_active = False
            target.save()
        elif action == 'activate':
            target.is_active = True
            target.save()
        elif action == 'approve':
            target_profile.is_approved = True
            target_profile.save()
        return redirect('admin_panel:user_management')
    all_profiles = Profile.objects.select_related('user').all()
    context = dict(profile=profile, active='users', all_profiles=all_profiles)
    return render(request, 'admin_panel/user_management.html', context)


@role_required('admin')
def opportunities(request):
    profile, detail = _admin_detail(request.user)
    form = None
    if request.method == 'POST' and request.POST.get('form_type') == 'create':
        form = OpportunityForm(request.POST)
        if form.is_valid():
            opp = form.save(commit=False)
            opp.status, opp.reviewed_by, opp.reviewed_at = 'open', request.user, timezone.now()
            opp.save()
            notes.notify_opportunity_published(opp)
            messages.success(request, f"{opp.title} is published and students were notified.")
            return redirect('admin_panel:opportunities')
        messages.error(request, "Please fix the errors in the form.")
    elif request.method == 'POST':
        opp = get_object_or_404(Opportunity, id=request.POST.get('opp_id'))
        action = request.POST.get('action')
        previous = opp.status
        if previous == 'draft':
            messages.error(request, "Drafts are private to their author and can't be reviewed yet.")
            return redirect('admin_panel:opportunities')
        if action == 'approve':
            opp.status = 'open'
        elif action == 'reject':
            opp.status = 'rejected'
            opp.review_note = (request.POST.get('review_note') or '').strip()[:300]
        elif action == 'close':
            opp.status = 'closed'
        else:
            messages.error(request, "Unknown action.")
            return redirect('admin_panel:opportunities')
        opp.reviewed_by = request.user
        opp.reviewed_at = timezone.now()
        opp.save()
        # Notify only on real transitions (never twice for the same publish).
        if opp.status == 'open' and previous in ('pending', 'rejected'):
            notes.notify_opportunity_published(opp)
            notes.notify_opportunity_review(opp, approved=True)
        elif opp.status == 'rejected' and previous != 'rejected':
            notes.notify_opportunity_review(opp, approved=False)
        messages.success(request, f"{opp.title}: {opp.get_status_display()}.")
        return redirect('admin_panel:opportunities')
    kind = request.GET.get('kind', '')
    status = request.GET.get('status', '')
    q = (request.GET.get('q') or '').strip()
    opps = Opportunity.objects.exclude(status='draft').select_related('posted_by_alumni').annotate(app_count=Count('applications'))
    if kind in ('job', 'internship'):
        opps = opps.filter(kind=kind)
    if status in dict(Opportunity.STATUS_CHOICES):
        opps = opps.filter(status=status)
    if q:
        opps = opps.filter(Q(title__icontains=q) | Q(company__icontains=q))
    page = Paginator(opps, 15).get_page(request.GET.get('page'))
    context = dict(profile=profile, active='opportunities', opportunities=page, page=page, qs_params=_qs(request), kind=kind, status=status, q=q,
                   status_choices=[c for c in Opportunity.STATUS_CHOICES if c[0] != 'draft'],
                   form=form or OpportunityForm(initial={'kind': kind or 'job'}))
    return render(request, 'admin_panel/opportunities.html', context)


@role_required('admin')
def courses(request):
    profile, detail = _admin_detail(request.user)
    if request.method == 'POST':
        Course.objects.create(
            title=request.POST.get('title'), provider=request.POST.get('provider', 'CareerMind Learning'),
            category=request.POST.get('category', 'Technical'),
            duration_weeks=request.POST.get('duration_weeks') or 4,
        )
        return redirect('admin_panel:courses')
    course_list = Course.objects.all()
    context = dict(profile=profile, active='courses', course_list=course_list)
    return render(request, 'admin_panel/courses.html', context)


@role_required('admin')
def mentorship(request):
    profile, detail = _admin_detail(request.user)
    requests_qs = MentorshipRequest.objects.select_related('student', 'alumni').all()
    context = dict(profile=profile, active='mentorship', requests_qs=requests_qs)
    return render(request, 'admin_panel/mentorship.html', context)


@role_required('admin')
def events(request):
    profile, detail = _admin_detail(request.user)
    if request.method == 'POST':
        title = (request.POST.get('title') or '').strip()
        try:
            event_date = datetime.date.fromisoformat(request.POST.get('event_date') or '')
        except ValueError:
            event_date = None
        if not title or not event_date:
            messages.error(request, "A title and a valid date are required.")
            return redirect('admin_panel:events')
        ev = CareerEvent.objects.create(
            title=title[:150], description=request.POST.get('description', ''), event_date=event_date,
            location=(request.POST.get('location') or 'Campus Auditorium')[:120],
            organizer=(request.POST.get('organizer') or 'Placement Cell')[:120],
            status='published', created_by=request.user, reviewed_by=request.user, reviewed_at=timezone.now(),
        )
        notes.notify_event_published(ev)
        messages.success(request, "Event published and students were notified.")
        return redirect('admin_panel:events')
    events_qs = CareerEvent.objects.filter(status='published').annotate(reg_count=Count('registrations'))
    context = dict(profile=profile, active='events', events=events_qs)
    return render(request, 'admin_panel/events.html', context)


@role_required('admin')
def workshops(request):
    """Approve / reject workshops & sessions submitted by Staff and Alumni."""
    profile, detail = _admin_detail(request.user)
    if request.method == 'POST':
        ev = get_object_or_404(CareerEvent, id=request.POST.get('event_id'))
        action = request.POST.get('action')
        previous = ev.status
        if previous == 'draft':
            messages.error(request, "Drafts are private to their author.")
            return redirect('admin_panel:workshops')
        if action == 'approve' and previous in ('pending', 'rejected'):
            ev.status = 'published'
        elif action == 'reject' and previous in ('pending', 'published'):
            ev.status = 'rejected'
            ev.review_note = (request.POST.get('review_note') or '').strip()[:300]
        elif action == 'cancel' and previous == 'published':
            ev.status = 'cancelled'
        else:
            messages.error(request, "That action isn't available for this session.")
            return redirect('admin_panel:workshops')
        ev.reviewed_by, ev.reviewed_at = request.user, timezone.now()
        ev.save()
        if ev.status == 'published':
            notes.notify_event_published(ev)
            notes.notify_event_review(ev, approved=True)
        elif ev.status == 'rejected':
            notes.notify_event_review(ev, approved=False)
        messages.success(request, f"{ev.title}: {ev.get_status_display()}.")
        return redirect('admin_panel:workshops')
    status = request.GET.get('status', '')
    qs = CareerEvent.objects.exclude(status='draft').select_related('created_by').annotate(reg_count=Count('registrations'))
    if status in dict(CareerEvent.STATUS_CHOICES):
        qs = qs.filter(status=status)
    qs = qs.order_by('-event_date')
    page = Paginator(qs, 15).get_page(request.GET.get('page'))
    context = dict(profile=profile, active='workshops', page=page, qs_params=_qs(request), status=status,
                   status_choices=[c for c in CareerEvent.STATUS_CHOICES if c[0] != 'draft'])
    return render(request, 'admin_panel/workshops.html', context)


@role_required('admin')
def applications(request):
    profile, detail = _admin_detail(request.user)
    if request.method == 'POST':
        app = get_object_or_404(Application.objects.select_related('opportunity', 'student'), id=request.POST.get('application_id'))
        new_status = request.POST.get('status', '')
        if new_status not in dict(Application.STATUS_CHOICES):
            messages.error(request, "Invalid status.")
        elif new_status != app.status:
            app.status = new_status
            app.save(update_fields=['status', 'updated_at'])
            notes.notify_application_status(app)
            messages.success(request, f"Status updated; {app.student.first_name or app.student.username} was notified.")
        return redirect(request.POST.get('next') if (request.POST.get('next') or '').startswith('/admin-panel/') else 'admin_panel:applications')
    status = request.GET.get('status', '')
    kind = request.GET.get('kind', '')
    q = (request.GET.get('q') or '').strip()
    qs = Application.objects.select_related('student', 'opportunity')
    if status in dict(Application.STATUS_CHOICES):
        qs = qs.filter(status=status)
    if kind in ('job', 'internship'):
        qs = qs.filter(opportunity__kind=kind)
    if q:
        qs = qs.filter(Q(opportunity__title__icontains=q) | Q(opportunity__company__icontains=q)
                       | Q(student__first_name__icontains=q) | Q(student__last_name__icontains=q))
    page = Paginator(qs, 15).get_page(request.GET.get('page'))
    context = dict(profile=profile, active='applications', page=page, qs_params=_qs(request), status=status, kind=kind, q=q,
                   status_choices=Application.STATUS_CHOICES)
    return render(request, 'admin_panel/applications.html', context)


@role_required('admin')
def announcements(request):
    profile, detail = _admin_detail(request.user)
    form = AnnouncementForm(request.POST or None) if request.POST.get('form_type') != 'toggle' else AnnouncementForm()
    if request.method == 'POST':
        if request.POST.get('form_type') == 'toggle':
            ann = get_object_or_404(Announcement, id=request.POST.get('announcement_id'))
            ann.is_active = not ann.is_active
            ann.save(update_fields=['is_active'])
            return redirect('admin_panel:announcements')
        if form.is_valid():
            ann = form.save(commit=False)
            ann.created_by = request.user
            ann.save()
            count = notes.notify_announcement(ann)
            messages.success(request, f"Announcement sent to {count} user(s).")
            return redirect('admin_panel:announcements')
    context = dict(profile=profile, active='announcements', form=form, items=Announcement.objects.select_related('created_by')[:50])
    return render(request, 'admin_panel/announcements.html', context)


@role_required('admin')
def learning_resources(request):
    profile, detail = _admin_detail(request.user)
    form = LearningResourceForm()
    if request.method == 'POST':
        if request.POST.get('form_type') == 'toggle':
            res = get_object_or_404(LearningResource, id=request.POST.get('resource_id'))
            res.is_active = not res.is_active
            res.save(update_fields=['is_active'])
            return redirect('admin_panel:learning_resources')
        form = LearningResourceForm(request.POST)
        if form.is_valid():
            res = form.save()
            count = notes.notify_learning_resource(res)
            messages.success(request, f"Resource added; {count} student(s) with a matching skill gap were notified.")
            return redirect('admin_panel:learning_resources')
    skill = (request.GET.get('skill') or '').strip()
    qs = LearningResource.objects.all()
    if skill:
        qs = qs.filter(skill__icontains=skill)
    page = Paginator(qs, 20).get_page(request.GET.get('page'))
    context = dict(profile=profile, active='learning_resources', form=form, page=page, qs_params=_qs(request), skill=skill)
    return render(request, 'admin_panel/learning_resources.html', context)


@role_required('admin')
def reports(request):
    profile, detail = _admin_detail(request.user)
    students_qs = Profile.objects.filter(role='student')
    total = students_qs.count()
    placed_ready = students_qs.filter(readiness_score__gte=80).count()
    context = dict(
        profile=profile, active='reports', total_students=total, placed_ready=placed_ready,
        chart_labels=["Q1", "Q2", "Q3", "Q4"],
        chart_values=[62, 68, 74, 80],
    )
    return render(request, 'admin_panel/reports.html', context)


@role_required('admin')
def notifications(request):
    return render_notification_page(request)


@role_required('admin')
def settings_view(request):
    profile, detail = _admin_detail(request.user)
    if request.method == 'POST':
        detail.designation = request.POST.get('designation', detail.designation)
        detail.save()
        return redirect('admin_panel:settings')
    context = dict(profile=profile, detail=detail, active='settings')
    return render(request, 'admin_panel/settings.html', context)
