from django.db import migrations, models


def verify_existing_users(apps, schema_editor):
    """Grandfather everyone who signed up before the gate existed.

    The field defaults to False, so without this every current member would be
    locked out of a working account by a link they never received.
    """
    apps.get_model('accounts', 'User').objects.update(email_verified=True)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_user_uuid'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='email_verified',
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(verify_existing_users, migrations.RunPython.noop),
    ]
