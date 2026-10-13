from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

from core.models import Profile


def _effective_role(user, profile):
    """The role the backend trusts. A Django superuser is always treated
    as Admin (this matches PortalLoginView, which already lets superusers
    into the Admin portal); everyone else is whatever Profile.role says."""
    if user.is_superuser:
        return 'admin'
    return profile.role


def role_required(role, *, redirect_wrong_role=False):
    """
    Restrict a view to users whose *database* role matches `role`.

    The role picked on the login screen is never consulted here. By default
    a wrong-role user gets a 403; with redirect_wrong_role=True (used for
    student pages, which are the site's default landing area) they are sent
    to their own dashboard instead of an error page.
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped(request, *args, **kwargs):
            profile, _ = Profile.objects.get_or_create(user=request.user)
            actual = _effective_role(request.user, profile)
            if actual != role:
                if redirect_wrong_role:
                    from core.views import ROLE_DASHBOARD_URL
                    return redirect(ROLE_DASHBOARD_URL.get(actual, 'landing'))
                raise PermissionDenied("You do not have access to this area of CareerMind.")
            # Faculty accounts stay locked until an Admin approves them, even
            # if a session somehow exists (e.g. approval revoked after login).
            if role == 'staff' and not profile.is_approved:
                raise PermissionDenied("Your Faculty account is pending Admin approval.")
            request.profile = profile
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


def student_required(view_func):
    """Student-portal views: non-students are redirected to their own portal."""
    return role_required('student', redirect_wrong_role=True)(view_func)
