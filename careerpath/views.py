from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.models import Profile
from core.metrics import sync_profile_metrics
from core.skill_matching import refresh_student_analysis
from roles.decorators import student_required

from .forms import CareerGoalForm
from .models import RoadmapMilestone, StudentCareerGoal
from .services import (
    build_career_feedback, build_career_summary, build_or_refresh_roadmap,
    classify_resume_domain, compute_skill_gap,
)


def _get_profile(user):
    profile, _created = Profile.objects.get_or_create(user=user)
    return profile


@student_required
def set_career_goal(request):
    profile = _get_profile(request.user)
    existing_goal = StudentCareerGoal.objects.filter(profile=profile).first()

    latest_resume = profile.resumes.first()
    detected_skills = latest_resume.skills if latest_resume else []
    detected_domain, domain_explanation = classify_resume_domain(detected_skills)

    if request.method == 'POST':
        form = CareerGoalForm(request.POST, instance=existing_goal)
        if form.is_valid():
            goal = form.save(commit=False)
            goal.profile = profile
            goal.save()

            # Keep the one shared notion of "target role" in sync so Skill
            # Analysis and the Learning Path follow the saved goal.
            profile.target_role = goal.role.name
            profile.save(update_fields=['target_role'])
            refresh_student_analysis(profile)
            sync_profile_metrics(profile)

            gap_result = compute_skill_gap(detected_skills, goal.company, goal.role)
            build_or_refresh_roadmap(goal, gap_result['gaps'])

            messages.success(request, "Career goal saved — your roadmap has been generated.")
            return redirect('careerpath:roadmap')
    else:
        form = CareerGoalForm(instance=existing_goal)

    context = dict(
        form=form,
        existing_goal=existing_goal,
        has_resume=latest_resume is not None,
        detected_domain=detected_domain,
        domain_explanation=domain_explanation,
        active="career_goal",
    )
    return render(request, 'careerpath/set_goal.html', context)


@student_required
def roadmap_page(request):
    profile = _get_profile(request.user)
    goal = StudentCareerGoal.objects.filter(profile=profile).select_related('domain', 'role', 'company').first()

    if not goal:
        messages.info(request, "Set your career goal first to generate a personalized roadmap.")
        return redirect('careerpath:set_goal')

    latest_resume = profile.resumes.first()
    detected_skills = latest_resume.skills if latest_resume else []

    gap_result = compute_skill_gap(detected_skills, goal.company, goal.role)
    roadmap = build_or_refresh_roadmap(goal, gap_result['gaps']) if not hasattr(goal, 'roadmap') else goal.roadmap

    # Keep the stored roadmap in sync with the current gap analysis, but
    # don't wipe milestone completion on every page view — only
    # (re)generate when there's no roadmap yet (handled above). A
    # student who wants a fresh plan after uploading a new resume uses
    # the "Recalculate" action below.
    milestones = roadmap.milestones.all()

    feedback = build_career_feedback(profile, goal, gap_result, roadmap)
    summary = build_career_summary(profile, goal, feedback)

    context = dict(
        profile=profile,
        goal=goal,
        has_resume=latest_resume is not None,
        gap_result=gap_result,
        roadmap=roadmap,
        milestones=milestones,
        feedback=feedback,
        summary=summary,
        active="career_roadmap",
    )
    return render(request, 'careerpath/roadmap.html', context)


@student_required
@require_POST
def recalculate_roadmap(request):
    """Regenerates the roadmap from the latest resume + current goal —
    used after the student uploads a new resume so gaps/roadmap reflect
    it, without requiring them to re-pick their goal."""
    profile = _get_profile(request.user)
    goal = get_object_or_404(StudentCareerGoal, profile=profile)

    latest_resume = profile.resumes.first()
    detected_skills = latest_resume.skills if latest_resume else []
    refresh_student_analysis(profile)
    sync_profile_metrics(profile)
    gap_result = compute_skill_gap(detected_skills, goal.company, goal.role)
    build_or_refresh_roadmap(goal, gap_result['gaps'])

    messages.success(request, "Roadmap recalculated from your latest resume.")
    return redirect('careerpath:roadmap')


@student_required
@require_POST
def toggle_milestone(request, milestone_id):
    profile = _get_profile(request.user)
    milestone = get_object_or_404(
        RoadmapMilestone, id=milestone_id, roadmap__goal__profile=profile,
    )
    milestone.is_completed = not milestone.is_completed
    milestone.completed_at = timezone.now() if milestone.is_completed else None
    milestone.save()
    return JsonResponse({
        "is_completed": milestone.is_completed,
        "roadmap_progress": milestone.roadmap.progress_percentage,
    })
