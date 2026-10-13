"""Student-facing career services: opportunities, applications, mentorship, workshops.
Every view is wrapped in `student_required`; every state change is POST-only."""
from django.contrib import messages
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from core.models import Profile

from . import notifications as notes
from .decorators import student_required
from .forms_career import ApplicationForm, MentorshipRequestForm
from .models import (AlumniDetail, Application, CareerEvent, EventRegistration,
                     MentorshipRequest, Opportunity)
from .services import published_opportunities, rank_opportunities, visible_events_for


def _profile(user):
    return Profile.objects.get_or_create(user=user)[0]


# ------------------------------------------------------------ opportunities
@student_required
def opportunities(request):
    profile = _profile(request.user)
    kind = request.GET.get('kind', 'job')
    if kind not in ('job', 'internship'):
        kind = 'job'
    q = (request.GET.get('q') or '').strip()
    etype = request.GET.get('type', '')
    sort = request.GET.get('sort', 'recommended')

    qs = published_opportunities(kind)
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(company__icontains=q) | Q(skills__icontains=q) | Q(location__icontains=q))
    if etype in dict(Opportunity.EMPLOYMENT_CHOICES):
        qs = qs.filter(employment_type=etype)

    items = rank_opportunities(profile, list(qs))
    if sort == 'newest':
        items.sort(key=lambda o: -o.created_at.timestamp())
    elif sort == 'deadline':
        items.sort(key=lambda o: (o.deadline is None, o.deadline or 0))

    applied = {a.opportunity_id: a for a in Application.objects.filter(student=request.user)}
    for o in items:
        o.application = applied.get(o.id)

    page = Paginator(items, 9).get_page(request.GET.get('page'))
    counts = {k: published_opportunities(k).count() for k in ('job', 'internship')}
    params = request.GET.copy()
    params.pop('page', None)
    return render(request, 'student/opportunities.html', dict(
        active='opportunities', kind=kind, page=page, q=q, etype=etype, sort=sort, counts=counts,
        employment_choices=Opportunity.EMPLOYMENT_CHOICES, qs_params=params.urlencode(),
        has_resume=profile.resumes.exists(),
    ))


def _visible_opportunity(request, pk):
    """Published opportunity, or one the student has already applied to."""
    opp = get_object_or_404(Opportunity.objects.select_related('posted_by_alumni', 'target_domain', 'target_role'), pk=pk)
    application = Application.objects.filter(student=request.user, opportunity=opp).first()
    if opp.status != 'open' and not application:
        raise Http404("Opportunity not available.")
    return opp, application


@student_required
def opportunity_detail(request, pk):
    profile = _profile(request.user)
    opp, application = _visible_opportunity(request, pk)
    opp = rank_opportunities(profile, [opp])[0]
    return render(request, 'student/opportunity_detail.html', dict(
        active='opportunities', opp=opp, application=application,
        can_apply=opp.status == 'open' and not opp.is_expired and not application,
    ))


@student_required
def opportunity_apply(request, pk):
    profile = _profile(request.user)
    opp, application = _visible_opportunity(request, pk)
    if application:
        messages.info(request, _("You have already applied to this opportunity."))
        return redirect('student:my_applications')
    if opp.status != 'open' or opp.is_expired:
        messages.error(request, _("Applications for this opportunity are closed."))
        return redirect('student:opportunity_detail', pk=opp.pk)

    resume = profile.resumes.first()
    form = ApplicationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                app = form.save(commit=False)
                app.student, app.opportunity, app.resume, app.status = request.user, opp, resume, 'applied'
                app.save()
        except IntegrityError:
            messages.info(request, _("You have already applied to this opportunity."))
            return redirect('student:my_applications')
        messages.success(request, _("Application submitted for %(title)s at %(company)s.") % {"title": opp.title, "company": opp.company})
        return redirect('student:my_applications')
    return render(request, 'student/apply.html', dict(active='opportunities', opp=opp, form=form, resume=resume))


@student_required
def my_applications(request):
    status = request.GET.get('status', '')
    qs = Application.objects.filter(student=request.user).select_related('opportunity', 'opportunity__posted_by_alumni')
    if status in dict(Application.STATUS_CHOICES):
        qs = qs.filter(status=status)
    page = Paginator(qs, 10).get_page(request.GET.get('page'))
    return render(request, 'student/my_applications.html', dict(
        active='applications', page=page, status=status, status_choices=Application.STATUS_CHOICES,
        total=Application.objects.filter(student=request.user).count(),
        qs_params=f"status={status}" if status in dict(Application.STATUS_CHOICES) else '',
    ))


# ---------------------------------------------------------------- mentorship
def _mentor_qs():
    return AlumniDetail.objects.filter(
        willing_to_mentor=True, profile__role='alumni', profile__user__is_active=True,
    ).select_related('profile__user')


@student_required
def find_mentor(request):
    q = (request.GET.get('q') or '').strip()
    industry = request.GET.get('industry', '')
    qs = _mentor_qs()
    if q:
        qs = qs.filter(
            Q(profile__user__first_name__icontains=q) | Q(profile__user__last_name__icontains=q)
            | Q(current_company__icontains=q) | Q(designation__icontains=q) | Q(industry__icontains=q)
            | Q(profile__skills__name__icontains=q)
        ).distinct()
    if industry:
        qs = qs.filter(industry=industry)
    qs = qs.order_by('profile__user__first_name')
    page = Paginator(qs, 9).get_page(request.GET.get('page'))

    mine = {}
    for mr in MentorshipRequest.objects.filter(student=request.user).order_by('created_at'):
        mine[mr.alumni_id] = mr  # latest wins
    for d in page:
        d.skill_names = [s.name for s in d.profile.skills.all()[:5]]
        d.my_request = mine.get(d.profile.user_id)
    industries = _mentor_qs().order_by('industry').values_list('industry', flat=True).distinct()
    params = request.GET.copy()
    params.pop('page', None)
    return render(request, 'student/find_mentor.html', dict(
        active='mentor', page=page, q=q, industry=industry, industries=industries, qs_params=params.urlencode()))


@student_required
def mentor_profile(request, user_id):
    detail = get_object_or_404(_mentor_qs(), profile__user_id=user_id)
    mentor = detail.profile.user
    skill_names = [s.name for s in detail.profile.skills.all()]
    existing = MentorshipRequest.objects.filter(student=request.user, alumni=mentor).first()
    return render(request, 'student/mentor_profile.html', dict(
        active='mentor', detail=detail, mentor=mentor, skill_names=skill_names, existing=existing,
        form=MentorshipRequestForm(),
    ))


@student_required
@require_POST
def request_mentorship(request, user_id):
    detail = get_object_or_404(_mentor_qs(), profile__user_id=user_id)
    mentor = detail.profile.user
    form = MentorshipRequestForm(request.POST)
    if MentorshipRequest.objects.filter(student=request.user, alumni=mentor, status='accepted').exists():
        messages.info(request, _("You are already connected with this mentor."))
        return redirect('student:my_mentorship')
    if MentorshipRequest.objects.filter(student=request.user, alumni=mentor, status='pending').exists():
        messages.info(request, _("You already have a pending request with this mentor."))
        return redirect('student:my_mentorship')
    if not form.is_valid():
        return render(request, 'student/mentor_profile.html', dict(
            active='mentor', detail=detail, mentor=mentor,
            skill_names=[s.name for s in detail.profile.skills.all()], existing=None, form=form))
    try:
        with transaction.atomic():
            mr = form.save(commit=False)
            mr.student, mr.alumni, mr.status = request.user, mentor, 'pending'
            mr.save()
    except IntegrityError:
        messages.info(request, _("You already have a pending request with this mentor."))
        return redirect('student:my_mentorship')
    notes.notify_mentorship_requested(mr)
    messages.success(request, _("Mentorship request sent. You'll be notified when the mentor responds."))
    return redirect('student:my_mentorship')


@student_required
def my_mentorship(request):
    status = request.GET.get('status', '')
    qs = MentorshipRequest.objects.filter(student=request.user).select_related('alumni', 'alumni__profile__alumni_detail')
    if status in ('pending', 'accepted', 'declined'):
        qs = qs.filter(status=status)
    return render(request, 'student/my_mentorship.html', dict(active='my_mentorship', requests_qs=qs, status=status))


# ---------------------------------------------------------------- workshops
@student_required
def workshops(request):
    profile = _profile(request.user)
    tab = request.GET.get('tab', 'upcoming')
    q = (request.GET.get('q') or '').strip()
    etype = request.GET.get('type', '')
    registered_ids = set(EventRegistration.objects.filter(student=request.user).values_list('event_id', flat=True))
    if tab == 'registered':
        qs = CareerEvent.objects.filter(pk__in=registered_ids, status='published').select_related('created_by', 'target_domain')
    else:
        tab = 'upcoming'
        qs = visible_events_for(profile)
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(topic__icontains=q) | Q(speaker__icontains=q))
    if etype in dict(CareerEvent.TYPE_CHOICES):
        qs = qs.filter(event_type=etype)
    page = Paginator(qs.order_by('event_date', 'event_time'), 9).get_page(request.GET.get('page'))
    for e in page:
        e.is_registered = e.id in registered_ids
    params = request.GET.copy()
    params.pop('page', None)
    return render(request, 'student/workshops.html', dict(
        active='workshops', page=page, tab=tab, q=q, etype=etype,
        type_choices=CareerEvent.TYPE_CHOICES, qs_params=params.urlencode()))


def _visible_event(request, pk):
    event = get_object_or_404(CareerEvent.objects.select_related('created_by', 'target_domain'), pk=pk)
    registered = EventRegistration.objects.filter(event=event, student=request.user).exists()
    if event.status != 'published' and not (registered and event.status == 'cancelled'):
        raise Http404("Workshop not available.")
    return event, registered


@student_required
def workshop_detail(request, pk):
    event, registered = _visible_event(request, pk)
    return render(request, 'student/workshop_detail.html', dict(
        active='workshops', event=event, registered=registered,
        reg_count=event.registrations.count()))


@student_required
@require_POST
def workshop_register(request, pk):
    event, registered = _visible_event(request, pk)
    if registered:
        messages.info(request, _("You are already registered for this session."))
    elif not event.registration_open:
        messages.error(request, _("Registration is closed for this session."))
    else:
        try:
            with transaction.atomic():
                EventRegistration.objects.create(event=event, student=request.user)
            messages.success(request, _("You're registered for %(title)s.") % {"title": event.title})
        except IntegrityError:
            messages.info(request, _("You are already registered for this session."))
    return redirect('student:workshop_detail', pk=event.pk)
