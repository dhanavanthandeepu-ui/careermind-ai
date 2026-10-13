import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Resume',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(upload_to='resumes/%Y/%m/')),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('raw_text', models.TextField(blank=True)),
                ('skills', models.JSONField(blank=True, default=list)),
                ('education', models.JSONField(blank=True, default=list)),
                ('projects', models.JSONField(blank=True, default=list)),
                ('certifications', models.JSONField(blank=True, default=list)),
                ('experience', models.JSONField(blank=True, default=list)),
                ('profile', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='resumes', to='core.profile')),
            ],
            options={
                'ordering': ['-uploaded_at'],
            },
        ),
    ]
