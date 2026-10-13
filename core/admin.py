from django.contrib import admin
from .models import Profile, Skill, Resume, LearningResource, StudentLearningProgress

admin.site.register(Profile)
admin.site.register(Skill)
admin.site.register(Resume)


@admin.register(LearningResource)
class LearningResourceAdmin(admin.ModelAdmin):
    list_display = ('skill', 'title', 'level', 'order', 'resource_type', 'is_active')
    list_filter = ('skill', 'level', 'resource_type', 'is_active')
    search_fields = ('skill', 'title')


@admin.register(StudentLearningProgress)
class StudentLearningProgressAdmin(admin.ModelAdmin):
    list_display = ('student', 'resource', 'status', 'started_at', 'completed_at')
    list_filter = ('status',)
