import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('roles', '0002_staffdetail_employee_id'),
        ('core', '0003_profile_is_approved'),
    ]

    operations = [
        migrations.CreateModel(
            name='StudentDetail',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('register_number', models.CharField(blank=True, default='', max_length=50)),
                ('department', models.CharField(blank=True, default='', max_length=120)),
                ('year', models.CharField(blank=True, default='', max_length=20)),
                ('profile', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='student_detail', to='core.profile')),
            ],
        ),
    ]
