from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_resume'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='is_approved',
            field=models.BooleanField(default=True),
        ),
    ]
