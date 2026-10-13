import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def tidy_existing_rows(apps, schema_editor):
    """Make existing data satisfy the new rules before constraints are added."""
    Opportunity = apps.get_model('roles', 'Opportunity')
    Opportunity.objects.filter(kind='internship').update(employment_type='internship')
    # At most one pending mentorship request per (student, alumni): keep the
    # newest, mark older duplicates as rejected ('declined').
    MentorshipRequest = apps.get_model('roles', 'MentorshipRequest')
    seen = set()
    for mr in MentorshipRequest.objects.filter(status='pending', alumni__isnull=False).order_by('-created_at', '-id'):
        key = (mr.student_id, mr.alumni_id)
        if key in seen:
            mr.status = 'declined'
            mr.save(update_fields=['status'])
        else:
            seen.add(key)


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('careerpath', '0001_initial'),
        ('core', '0005_honest_metric_defaults'),
        ('roles', '0005_resume_review_link'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ---- Opportunity ------------------------------------------------
        migrations.AddField(
            model_name='opportunity',
            name='employment_type',
            field=models.CharField(choices=[('full_time', 'Full-time'), ('part_time', 'Part-time'), ('contract', 'Contract'), ('internship', 'Internship'), ('other', 'Other')], default='full_time', max_length=12),
        ),
        migrations.AddField(
            model_name='opportunity',
            name='target_domain',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='opportunities', to='careerpath.careerdomain'),
        ),
        migrations.AddField(
            model_name='opportunity',
            name='target_role',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='opportunities', to='careerpath.careerrole'),
        ),
        migrations.AlterField(
            model_name='opportunity',
            name='status',
            field=models.CharField(choices=[('draft', 'Draft'), ('pending', 'Pending Approval'), ('open', 'Published'), ('rejected', 'Rejected'), ('closed', 'Closed')], default='open', max_length=12),
        ),

        # ---- CareerEvent (workshops / sessions) --------------------------
        migrations.AddField(
            model_name='careerevent',
            name='event_type',
            field=models.CharField(choices=[('event', 'Career Event'), ('workshop', 'Workshop'), ('seminar', 'Seminar'), ('technical', 'Technical Session'), ('guidance', 'Career Guidance Session'), ('placement', 'Placement Session'), ('training', 'Training Program'), ('industry_talk', 'Industry Talk'), ('resume_workshop', 'Resume Workshop'), ('interview_prep', 'Interview Preparation Session'), ('alumni_interaction', 'Alumni Interaction Session'), ('industry_experience', 'Industry Experience Session')], default='event', max_length=24),
        ),
        migrations.AddField(
            model_name='careerevent',
            name='speaker',
            field=models.CharField(blank=True, default='', max_length=120),
        ),
        migrations.AddField(
            model_name='careerevent',
            name='topic',
            field=models.CharField(blank=True, default='', max_length=120),
        ),
        migrations.AddField(
            model_name='careerevent',
            name='event_time',
            field=models.TimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='careerevent',
            name='mode',
            field=models.CharField(choices=[('offline', 'Offline'), ('online', 'Online')], default='offline', max_length=8),
        ),
        migrations.AddField(
            model_name='careerevent',
            name='meeting_link',
            field=models.URLField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='careerevent',
            name='registration_deadline',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='careerevent',
            name='target_domain',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='events', to='careerpath.careerdomain'),
        ),
        migrations.AddField(
            model_name='careerevent',
            name='banner',
            field=models.FileField(blank=True, upload_to='event_banners/%Y/%m/'),
        ),
        migrations.AddField(
            model_name='careerevent',
            name='status',
            field=models.CharField(choices=[('draft', 'Draft'), ('pending', 'Pending Approval'), ('published', 'Published'), ('rejected', 'Rejected'), ('cancelled', 'Cancelled')], default='published', max_length=10),
        ),
        migrations.AddField(
            model_name='careerevent',
            name='created_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_events', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='careerevent',
            name='review_note',
            field=models.CharField(blank=True, default='', max_length=300),
        ),
        migrations.AddField(
            model_name='careerevent',
            name='reviewed_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_events', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='careerevent',
            name='reviewed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='careerevent',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),

        # ---- MentorshipRequest -------------------------------------------
        migrations.AddField(
            model_name='mentorshiprequest',
            name='message',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='mentorshiprequest',
            name='responded_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='mentorshiprequest',
            name='status',
            field=models.CharField(choices=[('pending', 'Pending'), ('accepted', 'Accepted'), ('declined', 'Rejected'), ('completed', 'Completed')], default='pending', max_length=10),
        ),
        migrations.RunPython(tidy_existing_rows, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='mentorshiprequest',
            constraint=models.UniqueConstraint(condition=models.Q(('status', 'pending')), fields=('student', 'alumni'), name='uniq_pending_mentorship_per_pair'),
        ),

        # ---- Notification --------------------------------------------------
        migrations.AddField(
            model_name='notification',
            name='title',
            field=models.CharField(blank=True, default='', max_length=150),
        ),
        migrations.AddField(
            model_name='notification',
            name='notification_type',
            field=models.CharField(choices=[('workshop', 'Workshop'), ('seminar', 'Seminar'), ('job', 'Job'), ('internship', 'Internship'), ('mentorship', 'Mentorship'), ('application', 'Application status'), ('announcement', 'Announcement'), ('learning_resource', 'Learning resource'), ('career_update', 'Career update'), ('general', 'General')], default='general', max_length=20),
        ),
        migrations.AddField(
            model_name='notification',
            name='content_type',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='contenttypes.contenttype'),
        ),
        migrations.AddField(
            model_name='notification',
            name='object_id',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='notification',
            name='link',
            field=models.CharField(blank=True, default='', help_text='Internal path opened when the notification is clicked', max_length=255),
        ),
        migrations.AddField(
            model_name='notification',
            name='read_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='notification',
            name='message',
            field=models.CharField(max_length=300),
        ),
        migrations.AddIndex(
            model_name='notification',
            index=models.Index(fields=['recipient', 'is_read'], name='notif_recipient_read_idx'),
        ),

        # ---- New models ----------------------------------------------------
        migrations.CreateModel(
            name='Application',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cover_note', models.TextField(blank=True, default='')),
                ('status', models.CharField(choices=[('applied', 'Applied'), ('under_review', 'Under Review'), ('shortlisted', 'Shortlisted'), ('rejected', 'Rejected'), ('selected', 'Selected')], default='applied', max_length=14)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('opportunity', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='applications', to='roles.opportunity')),
                ('resume', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='applications', to='core.resume')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='applications', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
                'constraints': [models.UniqueConstraint(fields=('student', 'opportunity'), name='uniq_application_per_student_opportunity')],
            },
        ),
        migrations.CreateModel(
            name='EventRegistration',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('event', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='registrations', to='roles.careerevent')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='event_registrations', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
                'constraints': [models.UniqueConstraint(fields=('event', 'student'), name='uniq_registration_per_student_event')],
            },
        ),
        migrations.CreateModel(
            name='Announcement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=150)),
                ('message', models.TextField()),
                ('audience', models.CharField(choices=[('all', 'Everyone'), ('student', 'Students'), ('staff', 'Staff'), ('alumni', 'Alumni')], default='student', max_length=10)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='announcements', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
