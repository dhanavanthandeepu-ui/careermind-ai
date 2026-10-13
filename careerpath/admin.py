from django.contrib import admin

from .models import (
    Company, CareerDomain, CareerRole, Skill, RoleSkillRequirement,
    StudentCareerGoal, Roadmap, RoadmapMilestone,
)


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name',)


@admin.register(CareerDomain)
class CareerDomainAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


@admin.register(CareerRole)
class CareerRoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'domain', 'is_active')
    list_filter = ('domain', 'is_active')
    search_fields = ('name',)


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


@admin.register(RoleSkillRequirement)
class RoleSkillRequirementAdmin(admin.ModelAdmin):
    list_display = ('company', 'role', 'skill', 'priority', 'source', 'last_updated')
    list_filter = ('company', 'role', 'priority')
    search_fields = ('company__name', 'role__name', 'skill__name')
    autocomplete_fields = ('company', 'role', 'skill')


class RoadmapMilestoneInline(admin.TabularInline):
    model = RoadmapMilestone
    extra = 0


@admin.register(StudentCareerGoal)
class StudentCareerGoalAdmin(admin.ModelAdmin):
    list_display = ('profile', 'domain', 'role', 'company', 'timeline_months', 'updated_at')
    list_filter = ('domain', 'role', 'company', 'timeline_months')
    search_fields = ('profile__user__username',)


@admin.register(Roadmap)
class RoadmapAdmin(admin.ModelAdmin):
    list_display = ('goal', 'progress_percentage', 'generated_at')
    inlines = [RoadmapMilestoneInline]
