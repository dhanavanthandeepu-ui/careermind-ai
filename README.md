# CareerMind AI — Django Project

A Django recreation of the CareerMind AI academic career-intelligence platform
(landing page, signup/login, dashboard, skill gap analysis, resume analyzer,
learning roadmap, and AI chatbot), matching the maroon/gold/cream design from
the reference screenshots.

## Recent changes (integration pass)

- Role enforcement is done in the backend on every portal URL (`roles/decorators.py`);
  the role chosen on the login screen is never trusted. Student pages redirect other
  roles to their own dashboard; staff/alumni/admin pages return 403 to other roles.
- Student dashboard, Resume Analyzer, Skill Analysis and the AI assistant now show
  values computed from the student's real resume/goal data (`core/metrics.py`).
  Nothing is shown before a resume exists except an empty state.
- A saved Career Goal now drives Skill Analysis and the Learning Path
  (`core/skill_matching.resolve_requirements`); the original per-role list remains
  as the fallback when no goal/requirements exist.
- Alumni job/internship posts start as *Pending* and only appear to students after
  Admin approval (Approve / Reject / Close, with confirmation dialogs).
- Shared UI helpers: `static/js/app.js` (toasts, confirm dialogs via `data-confirm`,
  CSRF-aware `CM.post`).

Run `python manage.py test` (50 tests) after any change.

## Setup

```bash
python -m venv venv
source venv/bin/activate      # venv\Scripts\activate on Windows
pip install -r requirements.txt

python manage.py migrate
python manage.py seed_demo         # creates demo Staff/Alumni/Admin logins + sample data
python manage.py seed_companies    # companies / roles / skill requirements
python manage.py seed_learning_resources
python manage.py recompute_metrics # refresh derived student metrics (safe to re-run)
python manage.py createsuperuser   # optional, for /admin/
python manage.py runserver
```

Visit http://127.0.0.1:8000/

### Demo logins (created by `seed_demo`)

| Role   | Email                     | Password         |
|--------|---------------------------|-------------------|
| Staff  | `staff.demo@shc.edu`      | `CareerMind@2026` |
| Alumni | `alumni.demo@shc.edu`     | `CareerMind@2026` |
| Admin  | `admin.demo@shc.edu`      | `CareerMind@2026` |

Logging in through `/login/` now redirects each role to its own dashboard
automatically (Student → `/dashboard/`, Staff → `/staff/`, Alumni →
`/alumni/`, Admin → `/admin-panel/`). A new Student can still sign up at
`/signup/` exactly as before.

## Pages / routes

### Student (unchanged)

| URL                   | Page                                                     |
|------------------------|-----------------------------------------------------------|
| `/`                     | Marketing landing page                                    |
| `/signup/`              | Create account (also seeds mock skill data)                |
| `/login/`               | Login (portal-style role selector; redirects by role)      |
| `/dashboard/`           | Main dashboard                                             |
| `/skill-analysis/`      | Precision Skill Analysis (radar + bar charts, skill table) |
| `/resume-analyzer/`     | Resume Analyzer (score gauge, feedback, section breakdown) |
| `/learning-roadmap/`    | Learning Roadmap (milestone timeline, current task panel)  |
| `/chatbot/`             | AI Chatbot (live AJAX replies)                              |
| `/admin/`               | Django admin                                                |

### Staff (new)

| URL                         | Page |
|-------------------------------|-------|
| `/staff/`                     | Staff Dashboard |
| `/staff/students/`            | Students |
| `/staff/students/<id>/`       | Student Profile |
| `/staff/progress/`            | Student Progress |
| `/staff/resume-review/`       | Resume Review |
| `/staff/skill-analysis/`      | Skill Analysis |
| `/staff/career-guidance/`     | Career Guidance |
| `/staff/opportunities/`       | Jobs & Internships |
| `/staff/events/`              | Career Events |
| `/staff/reports/`             | Reports |
| `/staff/profile/`             | Staff Profile |

### Alumni (new)

| URL                         | Page |
|-------------------------------|-------|
| `/alumni/`                    | Alumni Dashboard |
| `/alumni/profile/`            | My Profile |
| `/alumni/career-journey/`     | Career Journey |
| `/alumni/skills/`             | Skills & Expertise |
| `/alumni/mentorship/`         | Mentorship (accept/decline) |
| `/alumni/students/`           | Students |
| `/alumni/opportunities/`      | Jobs & Internships (post + browse) |
| `/alumni/referrals/`          | Referrals |
| `/alumni/events/`             | Events |
| `/alumni/messages/`           | Messages |
| `/alumni/settings/`           | Settings |

### Admin (new)

| URL                         | Page |
|-------------------------------|-------|
| `/admin-panel/`               | Admin Dashboard |
| `/admin-panel/students/`      | Students |
| `/admin-panel/staff/`         | Staff |
| `/admin-panel/alumni/`        | Alumni |
| `/admin-panel/users/`         | User Management (activate/deactivate) |
| `/admin-panel/opportunities/` | Jobs & Internships (approve/close) |
| `/admin-panel/courses/`       | Courses (add new) |
| `/admin-panel/mentorship/`    | Mentorship |
| `/admin-panel/events/`        | Career Events (create new) |
| `/admin-panel/reports/`       | Reports & Analytics |
| `/admin-panel/notifications/` | Notifications |
| `/admin-panel/settings/`      | Settings |

Note: `/admin-panel/` is the new Admin **role** dashboard. Django's built-in
admin site is still at `/admin/`, unchanged.

## How it's put together

- Auth uses Django's built-in `User` model; the email address is used as the
  username (see `core/forms.py`).
- `core/models.py` defines `Profile` (readiness score, resume score, target
  role, etc.) and `Skill` (per-user skill inventory). A `Profile` plus a
  default skill set (`DEFAULT_SKILLS`) is created automatically on signup.
- All dashboard numbers are **mock/demo data** seeded per user — swap in real
  calculations (resume parsing, ML matching, etc.) by editing
  `core/views.py` and `core/models.py`.
- Charts (line, radar, bar, doughnut) use Chart.js via CDN; Tailwind CSS is
  loaded via the Tailwind CDN script for speed. Swap both for a real build
  pipeline (django-tailwind, a bundler, compiled Chart.js) before shipping to
  production.
- The chatbot's replies are simple keyword-based canned responses in
  `views.chatbot_reply` — swap that view for a real LLM/API call when ready.
- `templates/core/base.html` is the shared shell (sidebar + topbar) used by
  every logged-in page; `landing.html`, `login.html`, and `signup.html` are
  standalone full-page templates.

## Project structure

```
careermind/
├── careermind/          # project settings, urls
├── core/                # main app: models, views, forms, urls
│   └── migrations/
├── templates/core/       # all page templates
├── static/css/style.css  # theme (maroon/gold/cream palette)
├── manage.py
└── requirements.txt
```

## Career services (Student ↔ Staff ↔ Alumni ↔ Admin)

After pulling these changes run:

    python manage.py migrate        # applies roles.0006_career_services
    python manage.py test roles core

* Student: `/student/opportunities/`, `/student/applications/`, `/student/mentors/`, `/student/my-mentorship/`, `/student/workshops/`
* Everyone: `/notifications/` (filters, mark read / mark all read, header bell)
* Staff / Alumni: "My Workshops" / "Sessions & Workshops" (draft → pending → published), alumni "Jobs & Internships"
* Admin: Jobs & Internships, Workshops & Sessions, Applications, Announcements, Learning Resources
* Notifications are created only by real actions (see `roles/notifications.py`).

### Languages
Student pages, the header bell and notification texts are translated into Hindi, Tamil, Telugu, Kannada and Malayalam
(`locale/*/LC_MESSAGES/django.po`, compiled `.mo` files are included). Notification text is stored as a message id plus
parameters, so each reader sees it in their own language. Staff, alumni and admin pages remain English.
