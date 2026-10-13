from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('roles', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='staffdetail',
            name='employee_id',
            field=models.CharField(blank=True, default='', max_length=50),
        ),
    ]
