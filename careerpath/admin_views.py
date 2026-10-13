"""
Admin-panel page for the Company / CareerRole / Skill / RoleSkillRequirement
catalog. Lives in careerpath (not roles/views_admin.py) to keep the new
data model and its admin screen together, but reuses the existing
`role_required('admin')` decorator and renders inside the existing
admin_panel/base_admin.html shell, so it matches the rest of the admin
dashboard rather than introducing a second admin UI.
"""
from django.contrib import messages
from django.shortcuts import redirect, render

from roles.decorators import role_required

from .models import CareerDomain, CareerRole, Company, RoleSkillRequirement, Skill


@role_required('admin')
def career_requirements(request):
    if request.method == 'POST':
        form_type = request.POST.get('form_type')

        if form_type == 'add_company':
            name = (request.POST.get('name') or '').strip()
            if name:
                Company.objects.get_or_create(name=name)
                messages.success(request, f"Added company: {name}")

        elif form_type == 'toggle_company':
            company = Company.objects.filter(id=request.POST.get('company_id')).first()
            if company:
                company.is_active = not company.is_active
                company.save()
                messages.success(request, f"{company.name} is now {'active' if company.is_active else 'disabled'}.")

        elif form_type == 'add_domain':
            name = (request.POST.get('name') or '').strip()
            if name:
                CareerDomain.objects.get_or_create(name=name)
                messages.success(request, f"Added domain: {name}")

        elif form_type == 'add_role':
            domain = CareerDomain.objects.filter(id=request.POST.get('domain_id')).first()
            name = (request.POST.get('name') or '').strip()
            if domain and name:
                CareerRole.objects.get_or_create(domain=domain, name=name)
                messages.success(request, f"Added role: {name} ({domain.name})")

        elif form_type == 'add_requirement':
            company = Company.objects.filter(id=request.POST.get('company_id')).first()
            role = CareerRole.objects.filter(id=request.POST.get('role_id')).first()
            skill_name = (request.POST.get('skill_name') or '').strip()
            priority = request.POST.get('priority') or 'medium'
            source = (request.POST.get('source') or '').strip()
            if company and role and skill_name:
                skill, _ = Skill.objects.get_or_create(name=skill_name)
                defaults = {'priority': priority}
                if source:
                    defaults['source'] = source
                req, created = RoleSkillRequirement.objects.get_or_create(
                    company=company, role=role, skill=skill, defaults=defaults,
                )
                if not created:
                    req.priority = priority
                    if source:
                        req.source = source
                    req.save()
                messages.success(request, f"Saved requirement: {company.name} / {role.name} needs {skill.name}")

        elif form_type == 'delete_requirement':
            RoleSkillRequirement.objects.filter(id=request.POST.get('requirement_id')).delete()
            messages.success(request, "Requirement removed.")

        return redirect(request.path + (f"?company={request.POST.get('company_id')}" if request.POST.get('company_id') else ""))

    companies = Company.objects.all()
    domains = CareerDomain.objects.prefetch_related('roles').all()

    selected_company_id = request.GET.get('company')
    selected_company = companies.filter(id=selected_company_id).first() if selected_company_id else None
    requirements = (
        RoleSkillRequirement.objects.filter(company=selected_company).select_related('role', 'skill')
        if selected_company else RoleSkillRequirement.objects.none()
    )

    context = dict(
        active='career_requirements',
        companies=companies,
        domains=domains,
        selected_company=selected_company,
        requirements=requirements,
        priority_choices=RoleSkillRequirement._meta.get_field('priority').choices,
    )
    return render(request, 'admin_panel/career_requirements.html', context)
