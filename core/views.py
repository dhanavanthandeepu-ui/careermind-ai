import re

from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import LoginView
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.utils.translation import gettext as _
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST
from django.views.generic import CreateView

from roles.decorators import student_required
from .forms import SignUpForm
from .models import Profile, Resume
from .resume_parser import extract_text_from_pdf, parse_resume_sections
from .skill_matching import analyze_for_profile, apply_skill_match_to_profile, refresh_student_analysis


def landing(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    return render(request, 'core/landing.html')


class SignUpView(CreateView):
    form_class = SignUpForm
    template_name = 'core/signup.html'
    success_url = reverse_lazy('dashboard')

    def form_valid(self, form):
        response = super().form_valid(form)
        profile = Profile.objects.create(
            user=self.object,
            university_email=form.cleaned_data['email'],
            role='student',
            target_role=form.cleaned_data.get('target_role') or 'Cloud Solutions Architect',
        )
        from roles.models import StudentDetail
        StudentDetail.objects.create(
            profile=profile,
            register_number=form.cleaned_data['register_number'],
            department=form.cleaned_data['department'],
            year=form.cleaned_data['year'],
        )
        # No dummy Skill rows are seeded here anymore — the Skill Analysis
        # page now shows an empty state until the student actually
        # uploads a resume (see skill_analysis() and api_resume_upload()).
        login(self.request, self.object)
        return response


ROLE_DASHBOARD_URL = {
    'student': 'dashboard',
    'staff': 'staff:dashboard',
    'alumni': 'alumni:dashboard',
    'admin': 'admin_panel:dashboard',
}


class PortalLoginView(LoginView):
    template_name = 'core/login.html'
    authentication_form = AuthenticationForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        """
        Django authenticates the credentials via `form`, but the role the
        person clicked (Student/Faculty/Alumni/Admin) is never trusted by
        itself — we verify it against Profile.role in the database here,
        BEFORE calling super().form_valid() (which is what actually logs
        the session in). A mismatch never establishes a session at all.
        """
        selected_role = self.request.POST.get('role', 'student')
        user = form.get_user()
        profile, _created = Profile.objects.get_or_create(user=user)

        if selected_role == 'admin':
            # Per "use Django's existing superuser/admin mechanism": a
            # real Django superuser always qualifies; so does an account
            # an Admin has explicitly set role='admin' on (e.g. via the
            # admin site or seed_demo) — but nothing a public form can set.
            is_allowed = user.is_superuser or profile.role == 'admin'
        else:
            is_allowed = profile.role == selected_role

        if not is_allowed:
            form.add_error(None, "Those credentials are not registered for this portal. Please choose the correct role.")
            return self.form_invalid(form)

        if selected_role == 'staff' and not profile.is_approved:
            form.add_error(None, "Your Faculty account is still pending Admin approval.")
            return self.form_invalid(form)

        return super().form_valid(form)

    def get_success_url(self):
        from django.urls import reverse
        role = getattr(getattr(self.request.user, 'profile', None), 'role', 'student')
        url_name = ROLE_DASHBOARD_URL.get(role, 'dashboard')
        return reverse(url_name)


def logout_view(request):
    logout(request)
    return redirect('landing')


YOUTUBE_ID_RE = re.compile(r'(?:v=|youtu\.be/|embed/)([A-Za-z0-9_-]{11})')


def _youtube_thumbnail(url):
    """Best-effort YouTube thumbnail URL from a stored youtube_url. Returns
    None for links we can't extract an 11-char video id from (e.g. plain
    playlist URLs) — the template shows a plain labelled placeholder box
    in that case rather than a broken/fake image."""
    match = YOUTUBE_ID_RE.search(url or '')
    return f"https://img.youtube.com/vi/{match.group(1)}/hqdefault.jpg" if match else None


def _get_profile(user):
    profile, created = Profile.objects.get_or_create(user=user)
    # No dummy Skill rows are seeded here anymore — see SignUpView.form_valid.
    return profile


@student_required
def dashboard(request):
    from django.utils import timezone
    from careerpath.models import StudentCareerGoal
    from roles.models import Application, MentorshipRequest
    from roles.services import visible_events_for
    from .metrics import recommended_opportunities, sync_profile_metrics

    profile = _get_profile(request.user)
    snap = sync_profile_metrics(profile)  # also self-heals legacy fake values

    career_goal = StudentCareerGoal.objects.filter(profile=profile).select_related(
        'role', 'company',
    ).first()
    roadmap_progress = None
    if career_goal is not None and hasattr(career_goal, 'roadmap'):
        roadmap_progress = career_goal.roadmap.progress_percentage

    learning = _build_learning_path_data(profile, snap['has_resume'], snap['extraction_failed'])
    detected_all = snap['resume'].skills if snap['resume'] else []

    context = dict(
        profile=profile, snap=snap, learning=learning,
        career_goal=career_goal, roadmap_progress=roadmap_progress,
        jobs=recommended_opportunities(detected_all, 'job'),
        internships=recommended_opportunities(detected_all, 'internship'),
        events=visible_events_for(profile)[:4],
        application_count=Application.objects.filter(student=request.user).count(),
        pending_mentorship=MentorshipRequest.objects.filter(student=request.user, status='pending').count(),
        connected_mentors=MentorshipRequest.objects.filter(student=request.user, status='accepted').count(),
        top_gaps=snap['missing'][:4],
        active="dashboard",
    )
    return render(request, 'core/dashboard.html', context)


def _skill_cards(profile, priorities, label):
    """One dict per Skill row with real learning progress attached.
    Detection (current) is binary because the resume parser can only say
    'found' or 'not found'; growth/readiness come from the student's actual
    LearningResource completion for that skill."""
    from .models import LearningResource, StudentLearningProgress
    done_ids = set(
        StudentLearningProgress.objects.filter(student=profile, status='completed').values_list('resource_id', flat=True)
    )
    cards = []
    for sk in profile.skills.all():
        resources = list(LearningResource.objects.filter(skill__iexact=sk.name, is_active=True).order_by('order'))
        for r in resources:
            r.is_done = r.id in done_ids
        total = len(resources)
        completed = sum(1 for r in resources if r.is_done)
        detected = sk.current >= sk.target
        if detected:
            growth, readiness = 'Detected in resume', 100
        elif total and completed == total:
            growth, readiness = 'Learning complete', 100
        elif completed:
            growth, readiness = 'In progress', round(100 * completed / total)
        else:
            growth, readiness = 'Not started', 0
        cards.append(dict(
            skill=sk, detected=detected, growth=growth, readiness=readiness,
            gap=0 if detected else sk.target - sk.current,
            resources=resources, total=total, completed=completed,
            reason=label,
        ))
    # gaps first (highest priority first), then detected skills
    order = {'high': 0, 'medium': 1, 'low': 2}
    cards.sort(key=lambda c: (c['detected'], order.get(c['skill'].priority, 3), c['skill'].name))
    return cards


def _role_fit(detected_skills, limit=3):
    """Real role-fit: % of each tracked role's required skills that appear in
    the resume. Uses the same requirement lists as the gap analysis."""
    from .skill_matching import ROLE_SKILL_REQUIREMENTS, analyze_skill_match
    fits = []
    for role, required in ROLE_SKILL_REQUIREMENTS.items():
        a = analyze_skill_match(detected_skills, role, required=required)
        fits.append(dict(role=role, match=a['match_percentage'], missing=a['missing'], detected=a['detected']))
    fits.sort(key=lambda f: -f['match'])
    return fits[:limit]


@student_required
def skill_analysis(request):
    from .metrics import student_snapshot
    profile = _get_profile(request.user)
    snap = student_snapshot(profile)
    has_resume, extraction_failed = snap['has_resume'], snap['extraction_failed']
    ok = has_resume and not extraction_failed

    cards, radar_axes, radar_current, radar_target, role_fits = [], [], [], [], []
    if ok:
        cards = _skill_cards(profile, snap['priorities'], snap['target_label'])
        radar_axes = snap['required'][:6]
        radar_current = [100 if n in snap['detected'] else 0 for n in radar_axes]
        radar_target = [100 for _ in radar_axes]
        role_fits = _role_fit(snap['resume'].skills)

    gaps = [c for c in cards if not c['detected']]
    context = dict(
        profile=profile, snap=snap, has_resume=has_resume, extraction_failed=extraction_failed,
        cards=cards, gap_count=len(gaps), next_gap=gaps[0]['skill'].name if gaps else None,
        radar_axes=radar_axes, radar_current=radar_current, radar_target=radar_target,
        role_fits=role_fits, active="skill_analysis",
    )
    return render(request, 'core/skill_analysis.html', context)


MAX_RESUME_BYTES = 5 * 1024 * 1024  # 5 MB


@student_required
@ensure_csrf_cookie
def resume_analyzer(request):
    from .metrics import resume_feedback, student_snapshot
    profile = _get_profile(request.user)
    snap = student_snapshot(profile)
    feedback = resume_feedback(snap['resume_rows']) if snap['has_resume'] else []
    history = list(profile.resumes.all()[:10])
    from roles.models import ResumeReview
    review = ResumeReview.objects.filter(student=request.user).first()
    context = dict(profile=profile, snap=snap, feedback=feedback, history=history,
                   review=review, active="resume")
    # The upload JS re-fetches this page and swaps in #analysisResults, so a
    # partial-friendly single render path is used for first load and refresh.
    return render(request, 'core/resume_analyzer.html', context)


@student_required
def feedback_pdf(request):
    """
    "Download Feedback PDF": generated on the fly from the student's actual
    latest resume evaluation (never a static/pre-made file).
    """
    from django.contrib import messages
    from django.http import HttpResponse
    from django.utils import timezone
    from .metrics import resume_feedback, student_snapshot
    from .pdf_utils import build_feedback_pdf

    profile = _get_profile(request.user)
    snap = student_snapshot(profile)
    if not snap['has_resume']:
        messages.info(request, _("Upload your resume to begin your career analysis."))
        return redirect('resume_analyzer')

    student_name = request.user.get_full_name() or request.user.username
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="CareerMind_Feedback_Report.pdf"'
    build_feedback_pdf(
        response,
        student_name=student_name,
        target_career=snap['target_label'],
        feedback_date=timezone.now().strftime('%B %d, %Y'),
        rating=f"{snap['resume_score']}/100",
        category="Resume Analyzer",
        feedback_items=[f["text"] for f in resume_feedback(snap['resume_rows'])],
    )
    return response


def _build_learning_path_data(profile, has_resume, extraction_failed):
    """
    Computes everything the Learning Path page (and its progress-update
    endpoint) needs: the milestone stepper, the single-skill task list,
    and the richer per-skill data behind the interactive "Recommended
    Learning Videos" cards. Kept as one function so the page and the
    'Mark as Completed' endpoint always agree on the same numbers —
    there is exactly one place this is computed, not two.

    Nothing here is new business logic — this is the same
    analyze_skill_match + LearningResource/StudentLearningProgress
    lookups the page already used, only reorganized so it can be
    reused from api_learning_progress too.
    """
    from .models import LearningResource, StudentLearningProgress

    milestones = []
    tasks = []
    current_skill = None
    total_resources = 0
    completed_resources = 0
    skills_closed_count = 0
    gap_skills = []
    video_sections = []

    if has_resume and not extraction_failed:
        latest_resume = profile.resumes.first()
        analysis = analyze_for_profile(profile, latest_resume.skills)
        # Priority order = the order skills appear in the role's required
        # list (see ROLE_SKILL_REQUIREMENTS in skill_matching.py) — the
        # same order the Skill Analysis page uses for its deficit list.
        gap_skills = analysis["missing"]

        # profile.skills rows already carry real current/target/priority
        # for each required skill (see apply_skill_match_to_profile in
        # skill_matching.py) — reused here rather than re-deriving them.
        skill_rows = {s.name.strip().lower(): s for s in profile.skills.all()}

        current_found = False
        for skill_name in gap_skills:
            resources = list(
                LearningResource.objects.filter(skill__iexact=skill_name, is_active=True).order_by('order')
            )
            progress_by_resource = {
                p.resource_id: p
                for p in StudentLearningProgress.objects.filter(student=profile, resource__in=resources)
            }
            done_count = sum(
                1 for r in resources
                if progress_by_resource.get(r.id) and progress_by_resource[r.id].status == 'completed'
            )
            total_resources += len(resources)
            completed_resources += done_count

            for r in resources:
                r.thumbnail_url = _youtube_thumbnail(r.youtube_url)
                match = YOUTUBE_ID_RE.search(r.youtube_url or '')
                r.video_id = match.group(1) if match else None
                p = progress_by_resource.get(r.id)
                r.is_done = bool(p and p.status == 'completed')

            if resources and done_count == len(resources):
                state = 'done'
                skills_closed_count += 1
            elif not current_found:
                state = 'current'
                current_found = True
                current_skill = skill_name
                for r in resources:
                    tasks.append(dict(
                        resource_id=r.id,
                        text=r.title,
                        youtube_url=r.youtube_url,
                        done=r.is_done,
                    ))
            else:
                state = 'locked'

            skill_row = skill_rows.get(skill_name.strip().lower())
            video_sections.append(dict(
                skill=skill_name,
                state=state,
                current=skill_row.current if skill_row else 0,
                target=skill_row.target if skill_row else 100,
                priority=skill_row.priority if skill_row else 'high',
                priority_display=skill_row.get_priority_display() if skill_row else 'High',
                resources=resources,
            ))

            milestones.append(dict(stage="SKILL GAP", title=skill_name, state=state))

    overall_progress = round(100 * completed_resources / total_resources) if total_resources else 0

    return dict(
        milestones=milestones,
        tasks=tasks,
        current_skill=current_skill,
        gap_skills=gap_skills,
        video_sections=video_sections,
        overall_progress=overall_progress,
        total_resources=total_resources,
        completed_resources=completed_resources,
        skills_closed_count=skills_closed_count,
    )


@student_required
def learning_roadmap(request):
    profile = _get_profile(request.user)
    latest_resume = profile.resumes.first()
    has_resume = latest_resume is not None
    extraction_failed = has_resume and not latest_resume.skills

    data = _build_learning_path_data(profile, has_resume, extraction_failed)

    context = dict(
        profile=profile,
        has_resume=has_resume,
        extraction_failed=extraction_failed,
        milestones=data['milestones'],
        tasks=data['tasks'],
        current_skill=data['current_skill'],
        gap_skills=data['gap_skills'],
        video_sections=data['video_sections'],
        overall_progress=data['overall_progress'],
        total_resources=data['total_resources'],
        completed_resources=data['completed_resources'],
        skills_closed_count=data['skills_closed_count'],
        active="roadmap",
    )
    return render(request, 'core/learning_roadmap.html', context)


@student_required
@require_POST
def api_learning_progress(request, resource_id):
    """Marks one LearningResource Not Started / In Progress / Completed
    for the current student — what the Learning Path checkboxes (and
    the video cards' 'Mark as Completed' buttons) both call. There is
    only this one progress-tracking system; the video cards don't get
    a second one."""
    from django.shortcuts import get_object_or_404
    from django.utils import timezone
    from .models import LearningResource, StudentLearningProgress

    profile = _get_profile(request.user)
    resource = get_object_or_404(LearningResource, id=resource_id)
    new_status = request.POST.get('status', 'completed')
    if new_status not in ('not_started', 'in_progress', 'completed'):
        return JsonResponse({"error": "Invalid status."}, status=400)

    progress, _created = StudentLearningProgress.objects.get_or_create(student=profile, resource=resource)
    progress.status = new_status
    if new_status == 'in_progress' and not progress.started_at:
        progress.started_at = timezone.now()
    if new_status == 'completed' and not progress.completed_at:
        progress.completed_at = timezone.now()
    progress.save()

    latest_resume = profile.resumes.first()
    has_resume = latest_resume is not None
    extraction_failed = has_resume and not latest_resume.skills
    stats = _build_learning_path_data(profile, has_resume, extraction_failed)

    return JsonResponse({
        "message": "Progress updated.",
        "status": progress.status,
        "resource_id": resource.id,
        "overall_progress": stats['overall_progress'],
        "total_resources": stats['total_resources'],
        "completed_resources": stats['completed_resources'],
        "skills_closed_count": stats['skills_closed_count'],
    })


@student_required
def ai_chatbot(request):
    from .metrics import student_snapshot
    profile = _get_profile(request.user)
    snap = student_snapshot(profile)
    suggestions = [
        _("Review my placement readiness"),
        _("How is my resume?"),
        _("What are my skill gaps?"),
        _("What should I learn next?"),
    ]
    context = dict(profile=profile, snap=snap, suggestions=suggestions, active="chatbot")
    return render(request, 'core/ai_chatbot.html', context)


@student_required
@require_POST
def chatbot_reply(request):
    """
    Rule-based assistant (keyword intents, no LLM). Every answer is built from
    the student's own resume analysis, goal and learning progress; when the
    data doesn't exist yet it says so and points at the next step rather
    than inventing a number.
    """
    from .metrics import student_snapshot

    message = request.POST.get('message', '').strip().lower()
    profile = _get_profile(request.user)
    snap = student_snapshot(profile)
    no_resume = _("Upload your resume on the Resume Analyzer page to begin your career analysis.")

    if not message:
        return JsonResponse({'reply': _("Ask me about your readiness, resume, skill gaps or what to learn next.")})

    if any(w in message for w in ('readiness', 'ready', 'placement')):
        if snap['readiness'] is None:
            reply = no_resume
        else:
            reply = _("You currently match %(n)s of %(total)s required skills for %(role)s (%(pct)s%%).") % {
                'n': len(snap['detected']), 'total': len(snap['required']),
                'role': snap['target_label'], 'pct': snap['readiness'],
            }
    elif 'resume' in message:
        if snap['resume_score'] is None:
            reply = no_resume
        else:
            weakest = min(snap['resume_rows'], key=lambda r: r['fill'])
            reply = _("Your resume completeness score is %(score)s/100. The weakest section is %(sec)s (%(found)s detected).") % {
                'score': snap['resume_score'], 'sec': weakest['label'], 'found': weakest['found'],
            }
    elif 'gap' in message or 'skill' in message:
        if not snap['has_resume']:
            reply = no_resume
        elif snap['missing']:
            reply = _("Your current gaps for %(role)s: %(gaps)s.") % {
                'role': snap['target_label'], 'gaps': ", ".join(snap['missing']),
            }
        else:
            reply = _("You meet every tracked requirement for %(role)s.") % {'role': snap['target_label']}
    elif any(w in message for w in ('learn', 'next', 'study', 'course')):
        data = _build_learning_path_data(profile, snap['has_resume'], snap['extraction_failed'])
        if data['current_skill']:
            reply = _("Start with %(skill)s. Your Learning Path has the resources and tracks your progress.") % {
                'skill': data['current_skill']}
        elif snap['has_resume']:
            reply = _("You have no open skill gaps to learn right now.")
        else:
            reply = no_resume
    elif any(w in message for w in ('career', 'goal', 'role', 'path')):
        from careerpath.models import StudentCareerGoal
        goal = StudentCareerGoal.objects.filter(profile=profile).select_related('role', 'company').first()
        if goal:
            reply = _("Your goal is %(role)s at %(company)s within %(m)s months.") % {
                'role': goal.role.name, 'company': goal.company.name, 'm': goal.timeline_months}
        else:
            reply = _("You haven't set a career goal yet. Set one on the Career Roadmap page to get a personalised plan.")
    else:
        reply = _("I can help with your readiness, resume, skill gaps, what to learn next, or your career goal.")
    return JsonResponse({'reply': reply})


def api_test(request):
    """Simple connectivity check for the frontend-backend integration."""
    return JsonResponse({"message": "Backend connected successfully"})


@student_required
@require_POST
def api_resume_upload(request):
    """
    Accept a PDF resume upload, validate it (extension, size, real PDF
    header), store it, extract its text, and return the parsed sections plus
    the computed evaluation as JSON.

    Also (re)computes the student's skill match against their goal/target
    role and persists it via apply_skill_match_to_profile(), replacing any
    previous resume's analysis.
    """
    from .metrics import resume_evaluation, resume_feedback, sync_profile_metrics

    upload = request.FILES.get('resume')
    if not upload:
        return JsonResponse({"error": _("No file uploaded. Expected form field 'resume'.")}, status=400)

    if not upload.name.lower().endswith('.pdf'):
        return JsonResponse({"error": _("Only PDF files are supported.")}, status=400)

    if upload.size > MAX_RESUME_BYTES:
        return JsonResponse({"error": _("That file is too large. The maximum size is 5 MB.")}, status=400)

    # Extension alone is trivially spoofable: check the real PDF signature.
    head = upload.read(5)
    upload.seek(0)
    if head != b'%PDF-':
        return JsonResponse({"error": _("That file is not a valid PDF.")}, status=400)

    profile = _get_profile(request.user)
    resume = Resume.objects.create(profile=profile, file=upload)

    try:
        resume.file.seek(0)
        text = extract_text_from_pdf(resume.file)
    except Exception:
        resume.file.delete(save=False)
        resume.delete()
        return JsonResponse(
            {"error": _("Could not read this PDF. It may be corrupted or scanned as images.")},
            status=400,
        )

    sections = parse_resume_sections(text)

    resume.raw_text = text
    resume.skills = sections["skills"]
    resume.education = sections["education"]
    resume.projects = sections["projects"]
    resume.certifications = sections["certifications"]
    resume.experience = sections["experience"]
    resume.save()

    analysis_updated = False
    if resume.skills:
        # A new upload always fully supersedes the previous analysis.
        analysis = analyze_for_profile(profile, resume.skills)
        apply_skill_match_to_profile(profile, analysis)
        analysis_updated = True
    sync_profile_metrics(profile)

    score, rows = resume_evaluation(resume)
    return JsonResponse({
        "message": _("Resume analysed."),
        "resume_id": resume.id,
        "skills": resume.skills,
        "education": resume.education,
        "projects": resume.projects,
        "certifications": resume.certifications,
        "experience": resume.experience,
        "resume_score": score,
        "feedback": resume_feedback(rows),
        "skills_found": bool(resume.skills),
        "analysis_updated": analysis_updated,
    })


@student_required
@require_POST
def api_request_resume_review(request):
    """Student submits their latest resume for staff review. One open
    request at a time; resubmitting after staff asked for changes is allowed."""
    from roles.models import ResumeReview, StudentActivity
    profile = _get_profile(request.user)
    resume = profile.resumes.first()
    if resume is None:
        return JsonResponse({"error": _("Upload your resume first.")}, status=400)
    if ResumeReview.objects.filter(student=request.user, status='pending').exists():
        return JsonResponse({"error": _("Your resume is already waiting for review.")}, status=400)
    ResumeReview.objects.create(student=request.user, resume=resume)
    StudentActivity.objects.create(student=request.user, description="Submitted resume for staff review")
    return JsonResponse({"message": _("Resume submitted for review."), "status": "pending"})
