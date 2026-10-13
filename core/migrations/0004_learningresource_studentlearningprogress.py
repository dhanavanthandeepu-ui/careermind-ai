import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_profile_is_approved'),
    ]

    operations = [
        migrations.CreateModel(
            name='LearningResource',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('skill', models.CharField(db_index=True, max_length=100)),
                ('title', models.CharField(max_length=200)),
                ('description', models.TextField(blank=True, default='')),
                ('youtube_url', models.URLField()),
                ('level', models.CharField(choices=[('beginner', 'Beginner'), ('intermediate', 'Intermediate'), ('advanced', 'Advanced')], default='beginner', max_length=20)),
                ('duration', models.CharField(blank=True, default='', max_length=50)),
                ('order', models.PositiveIntegerField(default=1)),
                ('resource_type', models.CharField(choices=[('video', 'Video'), ('playlist', 'Playlist'), ('course', 'Course'), ('practice', 'Practice'), ('project', 'Project')], default='video', max_length=20)),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={
                'ordering': ['skill', 'order'],
            },
        ),
        migrations.CreateModel(
            name='StudentLearningProgress',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('not_started', 'Not Started'), ('in_progress', 'In Progress'), ('completed', 'Completed')], default='not_started', max_length=20)),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('resource', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='student_progress', to='core.learningresource')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='learning_progress', to='core.profile')),
            ],
            options={
                'unique_together': {('student', 'resource')},
            },
        ),
    ]
