"""
Notification generation. Every notification is created from a real database
action (an approval, a status change, a request...) by calling one of the
helpers below from the view that performed that action.
"""
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_noop as _n

from .models import Notification


def notify(users, title, message, notification_type='general', related=None, link='', params=None):
    """Create one Notification per distinct active user. Returns the count.

    `title` and `message` are translation msgids (marked with _n). `message` may
    contain %(name)s placeholders filled from `params`. The English text is stored
    in `message`; the msgid + params are stored too, so each reader sees the
    notification in *their own* language when it is displayed."""
    params = {k: str(v) for k, v in (params or {}).items()}
    key = message if params else ''
    if params:
        message = message % params
    ct = ContentType.objects.get_for_model(related) if related is not None else None
    seen, rows = set(), []
    for u in users:
        if u is None or u.pk in seen or not u.is_active:
            continue
        seen.add(u.pk)
        rows.append(Notification(
            recipient=u, title=title[:150], message=message[:300],
            notification_type=notification_type, content_type=ct,
            message_key=key[:300], message_params=params,
            object_id=related.pk if related is not None else None, link=link[:255],
        ))
    Notification.objects.bulk_create(rows)
    return len(rows)


def _full(user):
    return user.get_full_name() or user.username


# ------------------------------------------------------------ opportunities
def notify_admins_pending(obj, kind_label):
    admins = User.objects.filter(is_active=True).filter(Q(profile__role='admin') | Q(is_superuser=True)).distinct()
    return notify(admins, f"{kind_label} awaiting approval",
                  f"\"{obj.title}\" was submitted for review.", 'general', obj,
                  reverse('admin_panel:opportunities') if kind_label in ('Job', 'Internship')
                  else reverse('admin_panel:workshops'))


def notify_opportunity_published(opp):
    from .services import students_for_domain
    students = students_for_domain(opp.target_domain, opp.target_role)
    is_intern = opp.kind == 'internship'
    return notify(
        students, _n("New Internship Available") if is_intern else _n("New Job Available"),
        _n("%(title)s at %(company)s has been posted."),
        'internship' if is_intern else 'job', opp,
        reverse('student:opportunity_detail', args=[opp.pk]),
        params={'title': opp.title, 'company': opp.company},
    )


def notify_opportunity_review(opp, approved):
    if not opp.posted_by_alumni:
        return 0
    if approved:
        return notify([opp.posted_by_alumni], _n("Your posting was approved"),
                      _n('"%(title)s" is now visible to students.'), 'general', opp,
                      reverse('alumni:opportunities'), params={'title': opp.title})
    if opp.review_note:
        return notify([opp.posted_by_alumni], _n("Your posting was rejected"),
                      _n('"%(title)s" was not approved. Note: %(note)s'), 'general', opp,
                      reverse('alumni:opportunities'), params={'title': opp.title, 'note': opp.review_note})
    return notify([opp.posted_by_alumni], _n("Your posting was rejected"),
                  _n('"%(title)s" was not approved.'), 'general', opp,
                  reverse('alumni:opportunities'), params={'title': opp.title})


APPLICATION_MESSAGES = {
    'applied': _n("Your application for %(t)s at %(c)s has been received."),
    'under_review': _n("Your application for %(t)s at %(c)s is under review."),
    'shortlisted': _n("Congratulations! Your application for %(t)s at %(c)s has been shortlisted."),
    'rejected': _n("Your application for %(t)s at %(c)s was not successful this time."),
    'selected': _n("Congratulations! You have been selected for %(t)s at %(c)s."),
}


def notify_application_status(app):
    opp = app.opportunity
    return notify([app.student], _n("Application update"), APPLICATION_MESSAGES[app.status], 'application', app,
                  reverse('student:my_applications'), params={'t': opp.title, 'c': opp.company})


# --------------------------------------------------------------- workshops
def notify_event_published(event):
    from .services import students_for_domain
    students = students_for_domain(event.target_domain)
    title = _n("New Career Seminar") if event.event_type == 'seminar' else _n("New Career Workshop")
    return notify(students, title, _n("%(title)s has been scheduled for %(date)s."),
                  event.notification_type, event, event.get_student_url(),
                  params={'title': event.title, 'date': event.event_date.isoformat()})


def notify_event_review(event, approved):
    if not event.created_by:
        return 0
    if approved:
        return notify([event.created_by], _n("Your session was approved"),
                      _n('"%(title)s" is published and students were notified.'), 'general', event,
                      _owner_list_url(event), params={'title': event.title})
    if event.review_note:
        return notify([event.created_by], _n("Your session was rejected"),
                      _n('"%(title)s" was not approved. Note: %(note)s'), 'general', event, _owner_list_url(event),
                      params={'title': event.title, 'note': event.review_note})
    return notify([event.created_by], _n("Your session was rejected"),
                  _n('"%(title)s" was not approved.'), 'general', event, _owner_list_url(event),
                  params={'title': event.title})


def _owner_list_url(event):
    role = getattr(getattr(event.created_by, 'profile', None), 'role', '')
    return reverse('alumni:workshops') if role == 'alumni' else reverse('staff:workshops')


# --------------------------------------------------------------- mentorship
def notify_mentorship_requested(mr):
    if not mr.alumni:
        return 0
    return notify([mr.alumni], _n("New mentorship request"),
                  _n("New mentorship request from %(name)s."), 'mentorship', mr,
                  reverse('alumni:mentorship'), params={'name': _full(mr.student)})


def notify_mentorship_response(mr):
    who = _full(mr.alumni) if mr.alumni else '—'
    if mr.status == 'accepted':
        title, msg = _n("Mentorship request accepted"), _n("Your mentorship request has been accepted by %(name)s.")
    else:
        title, msg = _n("Mentorship request rejected"), _n("Your mentorship request to %(name)s was not accepted.")
    return notify([mr.student], title, msg, 'mentorship', mr, reverse('student:my_mentorship'),
                  params={'name': who})


# ------------------------------------------------------ announcements, etc.
def notify_announcement(ann):
    qs = User.objects.filter(is_active=True)
    if ann.audience != 'all':
        qs = qs.filter(profile__role=ann.audience)
    return notify(qs, ann.title, ann.message, 'announcement', ann, reverse('notifications'))


def notify_learning_resource(resource):
    """Tell students whose current skill gaps include this resource's skill."""
    from core.models import Profile
    from core.skill_matching import analyze_for_profile
    targets = []
    for p in Profile.objects.filter(role='student').select_related('user'):
        latest = p.resumes.first()
        if latest and latest.skills:
            missing = {m.lower() for m in analyze_for_profile(p, latest.skills)['missing']}
            if resource.skill.lower() in missing:
                targets.append(p.user)
    return notify(targets, _n("New learning resource"),
                  _n("%(title)s was added for %(skill)s."), 'learning_resource', resource,
                  reverse('learning_roadmap'), params={'title': resource.title, 'skill': resource.skill})


def notify_guidance_update(gr):
    return notify([gr.student], _n("Career guidance update"),
                  _n('Your guidance request "%(topic)s" is now %(status)s.'),
                  'career_update', gr, reverse('dashboard'),
                  params={'topic': gr.topic, 'status': gr.get_status_display().lower()})


# ------------------------------------------------------------ read / unread
def unread_count(user):
    return Notification.objects.filter(recipient=user, is_read=False).count()


def mark_read(notification):
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save(update_fields=['is_read', 'read_at'])


def mark_all_read(user):
    return Notification.objects.filter(recipient=user, is_read=False).update(is_read=True, read_at=timezone.now())
