from django.contrib.auth.models import User
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.models import Profile
from . import notifications as notes
from . import views_workshops as ws
from .decorators import role_required
from .forms_career import OpportunityForm
from .models import (
    AlumniDetail, Opportunity, CareerEvent, MentorshipRequest,
    Referral, Message,
)


def _alumni_detail(user):
    profile, _ = Profile.objects.get_or_create(user=user)
    detail, _ = AlumniDetail.objects.get_or_create(profile=profile)
    return profile, detail


@role_required('alumni')
def dashboard(request):
    profile, detail = _alumni_detail(request.user)
    mentorship_requests = MentorshipRequest.objects.filter(alumni=request.user, status='pending').select_related('student')
    connected_students = MentorshipRequest.objects.filter(alumni=request.user, status='accepted').select_related('student')
    my_posts = Opportunity.objects.filter(posted_by_alumni=request.user)
    opportunities = my_posts[:5]
    today = timezone.localdate()
    my_events = CareerEvent.objects.filter(created_by=request.user)
    upcoming_events = CareerEvent.objects.filter(status='published', event_date__gte=today)[:4]
    recent_messages = Message.objects.filter(recipient=request.user).select_related('sender')[:5]
    status_counts = {code: my_posts.filter(status=code).count() for code, _ in Opportunity.STATUS_CHOICES}
    context = dict(
        profile=profile, detail=detail, active='dashboard',
        mentorship_requests=mentorship_requests, connected_students=connected_students,
        opportunities=opportunities, upcoming_events=upcoming_events, recent_messages=recent_messages,
        job_count=my_posts.filter(kind='job').count(), internship_count=my_posts.filter(kind='internship').count(),
        status_counts=status_counts,
        my_workshops=my_events.order_by('-event_date')[:5], workshop_count=my_events.count(),
        pending_workshops=my_events.filter(status='pending').count(),
        upcoming_workshops=my_events.filter(status='published', event_date__gte=today).count(),
        completed_workshops=my_events.filter(status='published', event_date__lt=today).count(),
    )
    return render(request, 'alumni/dashboard.html', context)


@role_required('alumni')
def profile_view(request):
    profile, detail = _alumni_detail(request.user)
    if request.method == 'POST':
        detail.current_company = request.POST.get('current_company', detail.current_company)
        detail.designation = request.POST.get('designation', detail.designation)
        detail.industry = request.POST.get('industry', detail.industry)
        detail.bio = request.POST.get('bio', detail.bio)
        detail.save()
        return redirect('alumni:profile')
    context = dict(profile=profile, detail=detail, active='profile')
    return render(request, 'alumni/profile.html', context)


@role_required('alumni')
def career_journey(request):
    profile, detail = _alumni_detail(request.user)
    context = dict(profile=profile, detail=detail, active='journey')
    return render(request, 'alumni/career_journey.html', context)


@role_required('alumni')
def skills(request):
    profile, detail = _alumni_detail(request.user)
    context = dict(profile=profile, detail=detail, active='skills', skills=profile.skills.all())
    return render(request, 'alumni/skills.html', context)


@role_required('alumni')
def mentorship(request):
    profile, detail = _alumni_detail(request.user)
    if request.method == 'POST':
        action = request.POST.get('action')
        mr = get_object_or_404(MentorshipRequest, id=request.POST.get('request_id'), alumni=request.user)
        if mr.status != 'pending':
            messages.info(request, "That request has already been answered.")
            return redirect('alumni:mentorship')
        if action == 'accept':
            mr.status = 'accepted'
        elif action in ('reject', 'decline'):
            mr.status = 'declined'
        else:
            messages.error(request, "Unknown action.")
            return redirect('alumni:mentorship')
        mr.responded_at = timezone.now()
        mr.save(update_fields=['status', 'responded_at'])
        notes.notify_mentorship_response(mr)
        messages.success(request, "Request accepted. The student is now a connected mentee." if mr.status == 'accepted'
                         else "Request rejected.")
        return redirect('alumni:mentorship')
    qs = MentorshipRequest.objects.filter(alumni=request.user).select_related(
        'student', 'student__profile', 'student__profile__career_goal__role', 'student__profile__career_goal__domain')
    for m in qs:
        goal = getattr(m.student.profile, 'career_goal', None) if hasattr(m.student, 'profile') else None
        m.goal = goal
    context = dict(
        profile=profile, detail=detail, active='mentorship',
        pending=[m for m in qs if m.status == 'pending'],
        connected=[m for m in qs if m.status == 'accepted'],
        past=[m for m in qs if m.status == 'declined'],
    )
    return render(request, 'alumni/mentorship.html', context)


@role_required('alumni')
def students(request):
    profile, detail = _alumni_detail(request.user)
    student_list = Profile.objects.filter(role='student').select_related('user')[:30]
    context = dict(profile=profile, active='students', student_list=student_list)
    return render(request, 'alumni/students.html', context)


@role_required('alumni')
def opportunities(request):
    """List of the alumnus's own postings (jobs / internships) + quick-post form.
    The full form (skills, eligibility, deadline, domain/role...) is opportunity_new."""
    profile, detail = _alumni_detail(request.user)
    if request.method == 'POST':
        title = (request.POST.get('title') or '').strip()
        company = (request.POST.get('company') or '').strip()
        kind = request.POST.get('kind', 'job')
        if not title or not company or kind not in ('job', 'internship'):
            messages.error(request, "Title, company and a valid type are required.")
            return redirect('alumni:opportunities')
        # Alumni posts never go live on their own: they wait for Admin approval.
        opp = Opportunity.objects.create(
            title=title[:150], company=company[:120], kind=kind,
            employment_type='internship' if kind == 'internship' else 'full_time',
            location=(request.POST.get('location') or 'Remote').strip()[:120],
            pay=(request.POST.get('pay') or '').strip()[:80],
            status='pending', posted_by_alumni=request.user,
        )
        notes.notify_admins_pending(opp, 'Internship' if kind == 'internship' else 'Job')
        messages.success(request, "Submitted for admin approval. It will be visible to students once approved.")
        return redirect('alumni:opportunities')
    kind = request.GET.get('kind', '')
    my_opps = Opportunity.objects.filter(posted_by_alumni=request.user).select_related('target_domain', 'target_role')
    if kind in ('job', 'internship'):
        my_opps = my_opps.filter(kind=kind)
    status = request.GET.get('status', '')
    if status in dict(Opportunity.STATUS_CHOICES):
        my_opps = my_opps.filter(status=status)
    context = dict(profile=profile, active='opportunities', my_opps=my_opps, kind=kind, status=status,
                   status_choices=Opportunity.STATUS_CHOICES)
    return render(request, 'alumni/opportunities.html', context)


def _save_opportunity(request, form, instance_user):
    opp = form.save(commit=False)
    opp.posted_by_alumni = instance_user
    submit = request.POST.get('action') == 'submit'
    # Alumni posts never go live on their own: draft or pending, never 'open'.
    opp.status = 'pending' if submit else 'draft'
    if submit:
        opp.review_note = ''
    opp.save()
    if submit:
        notes.notify_admins_pending(opp, 'Internship' if opp.kind == 'internship' else 'Job')
        messages.success(request, "Submitted for admin approval. It will be visible to students once approved.")
    else:
        messages.success(request, "Draft saved.")


@role_required('alumni')
def opportunity_form(request, pk=None):
    profile, detail = _alumni_detail(request.user)
    opp = get_object_or_404(Opportunity, pk=pk, posted_by_alumni=request.user) if pk else None
    if opp and opp.status not in ('draft', 'rejected'):
        messages.error(request, "Only drafts and rejected postings can be edited.")
        return redirect('alumni:opportunities')
    initial = {'company': detail.current_company} if (not opp and detail.current_company not in ('', '—')) else None
    form = OpportunityForm(request.POST or None, instance=opp, initial=initial)
    if request.method == 'POST' and form.is_valid():
        _save_opportunity(request, form, request.user)
        return redirect('alumni:opportunities')
    return render(request, 'alumni/opportunity_form.html', dict(profile=profile, active='opportunities', form=form, opp=opp))


@role_required('alumni')
@require_POST
def opportunity_action(request, pk):
    opp = get_object_or_404(Opportunity, pk=pk, posted_by_alumni=request.user)
    action = request.POST.get('action')
    if action == 'submit' and opp.status in ('draft', 'rejected'):
        opp.status, opp.review_note = 'pending', ''
        opp.save(update_fields=['status', 'review_note'])
        notes.notify_admins_pending(opp, 'Internship' if opp.kind == 'internship' else 'Job')
        messages.success(request, "Submitted for admin approval.")
    elif action == 'delete' and opp.status in ('draft', 'rejected'):
        opp.delete()
        messages.success(request, "Posting deleted.")
    elif action == 'close' and opp.status == 'open':
        opp.status = 'closed'
        opp.save(update_fields=['status'])
        messages.success(request, "Posting closed. Students can no longer apply.")
    else:
        messages.error(request, "That action isn't available for this posting.")
    return redirect('alumni:opportunities')


@role_required('alumni')
def opportunity_applicants(request, pk):
    """Read-only list of applicants to the alumnus's own posting."""
    profile, detail = _alumni_detail(request.user)
    opp = get_object_or_404(Opportunity, pk=pk, posted_by_alumni=request.user)
    apps = opp.applications.select_related('student')
    return render(request, 'alumni/applicants.html', dict(profile=profile, active='opportunities', opp=opp, apps=apps))


@role_required('alumni')
def referrals(request):
    profile, detail = _alumni_detail(request.user)
    referral_list = Referral.objects.filter(alumni=request.user).select_related('student', 'opportunity')
    context = dict(profile=profile, active='referrals', referral_list=referral_list)
    return render(request, 'alumni/referrals.html', context)


@role_required('alumni')
def events(request):
    profile, detail = _alumni_detail(request.user)
    events_qs = CareerEvent.objects.filter(status='published')
    context = dict(profile=profile, active='events', events=events_qs)
    return render(request, 'alumni/events.html', context)


@role_required('alumni')
def messages_view(request):
    profile, detail = _alumni_detail(request.user)
    if request.method == 'POST':
        recipient_id = request.POST.get('recipient_id')
        body = request.POST.get('body')
        if recipient_id and body:
            Message.objects.create(sender=request.user, recipient_id=recipient_id, body=body)
        return redirect('alumni:messages')
    inbox = Message.objects.filter(recipient=request.user).select_related('sender')
    sent = Message.objects.filter(sender=request.user).select_related('recipient')
    context = dict(profile=profile, active='messages', inbox=inbox, sent=sent)
    return render(request, 'alumni/messages.html', context)


@role_required('alumni')
def settings_view(request):
    profile, detail = _alumni_detail(request.user)
    if request.method == 'POST':
        detail.willing_to_mentor = bool(request.POST.get('willing_to_mentor'))
        detail.save()
        return redirect('alumni:settings')
    context = dict(profile=profile, detail=detail, active='settings')
    return render(request, 'alumni/settings.html', context)


# ------------------------------------------------------- workshops / sessions
@role_required('alumni')
def workshops(request):
    return ws.my_workshops(request, 'alumni')


@role_required('alumni')
def workshop_new(request):
    return ws.workshop_form(request, 'alumni')


@role_required('alumni')
def workshop_edit(request, pk):
    return ws.workshop_form(request, 'alumni', pk)


@role_required('alumni')
@require_POST
def workshop_action(request, pk):
    return ws.workshop_action(request, 'alumni', pk)


@role_required('alumni')
def workshop_registrations(request, pk):
    return ws.workshop_registrations(request, 'alumni', pk)
