from django.db import migrations, models


def grandfather_existing_users(apps, schema_editor):
    """Never prompt anyone who signed up before the phone field existed.

    `phone_required` defaults to True so every *new* account is asked for a
    number on first sign-in. Existing members already use the site and were
    never asked, so flipping them to False keeps them out of the prompt.
    """
    apps.get_model('accounts', 'User').objects.update(phone_required=False)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0005_socialaccount_socialaccount_unique_social_identity'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='phone',
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddField(
            model_name='user',
            name='phone_required',
            field=models.BooleanField(default=True),
        ),
        migrations.RunPython(grandfather_existing_users, migrations.RunPython.noop),
    ]
