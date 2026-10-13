import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('core', '0004_learningresource_studentlearningprogress'),
    ]

    operations = [
        migrations.CreateModel(
            name='Company',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120, unique=True)),
                ('is_active', models.BooleanField(default=True, help_text='Uncleared companies stay in the database but are hidden from the student-facing goal picker (soft delete / disable).')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name_plural': 'Companies',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='CareerDomain',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120, unique=True)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='Skill',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='CareerRole',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120)),
                ('is_active', models.BooleanField(default=True)),
                ('domain', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='roles', to='careerpath.careerdomain')),
            ],
            options={
                'ordering': ['domain__name', 'name'],
                'unique_together': {('domain', 'name')},
            },
        ),
        migrations.CreateModel(
            name='RoleSkillRequirement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('priority', models.CharField(choices=[('critical', 'Critical'), ('high', 'High'), ('medium', 'Medium'), ('low', 'Low')], default='medium', max_length=10)),
                ('source', models.CharField(default='Generic industry baseline (not company-verified) — update via Admin.', max_length=255)),
                ('last_updated', models.DateField(auto_now=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='requirements', to='careerpath.company')),
                ('role', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='requirements', to='careerpath.careerrole')),
                ('skill', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='requirements', to='careerpath.skill')),
            ],
            options={
                'ordering': ['company__name', 'role__name', 'priority'],
                'unique_together': {('company', 'role', 'skill')},
            },
        ),
        migrations.CreateModel(
            name='StudentCareerGoal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('timeline_months', models.PositiveIntegerField(choices=[(3, '3 Months'), (6, '6 Months'), (9, '9 Months'), (12, '12 Months')], default=6)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to='careerpath.company')),
                ('domain', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to='careerpath.careerdomain')),
                ('role', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='+', to='careerpath.careerrole')),
                ('profile', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='career_goal', to='core.profile')),
            ],
        ),
        migrations.CreateModel(
            name='Roadmap',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('generated_at', models.DateTimeField(auto_now=True)),
                ('goal', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='roadmap', to='careerpath.studentcareergoal')),
            ],
        ),
        migrations.CreateModel(
            name='RoadmapMilestone',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('month_number', models.PositiveIntegerField()),
                ('title', models.CharField(max_length=200)),
                ('tasks', models.JSONField(blank=True, default=list)),
                ('is_completed', models.BooleanField(default=False)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('roadmap', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='milestones', to='careerpath.roadmap')),
            ],
            options={
                'ordering': ['month_number'],
                'unique_together': {('roadmap', 'month_number')},
            },
        ),
    ]
