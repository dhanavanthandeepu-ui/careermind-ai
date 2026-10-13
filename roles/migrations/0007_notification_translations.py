from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('roles', '0006_career_services'),
    ]

    operations = [
        migrations.AddField(
            model_name='notification',
            name='message_key',
            field=models.CharField(blank=True, default='', max_length=300),
        ),
        migrations.AddField(
            model_name='notification',
            name='message_params',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
