from django.shortcuts import render, redirect

from core.models import Profile
from .forms import FacultySignUpForm
from .models import StaffDetail


def faculty_signup(request):
    """
    Public Faculty registration. Creates a Profile with role='staff' and
    is_approved=False — the account cannot log in (see PortalLoginView)
    until an Admin approves it from User Management.
    """
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = FacultySignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            profile = Profile.objects.create(
                user=user,
                university_email=form.cleaned_data['email'],
                role='staff',
                is_approved=False,
            )
            StaffDetail.objects.create(
                profile=profile,
                employee_id=form.cleaned_data['employee_id'],
                department=form.cleaned_data['department'],
                designation=form.cleaned_data['designation'],
            )
            return render(request, 'core/faculty_signup_pending.html')
    else:
        form = FacultySignUpForm()

    return render(request, 'core/faculty_signup.html', {'form': form})
