import uuid

from django.db import migrations, models


def populate_uuids(apps, schema_editor):
    """Give every existing user a distinct UUID before we enforce uniqueness."""
    User = apps.get_model('accounts', 'User')
    for user in User.objects.all().only('id'):
        User.objects.filter(pk=user.pk).update(uuid=uuid.uuid4())


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        # 1) Add nullable so existing rows don't collide on the unique index.
        migrations.AddField(
            model_name='user',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid4, editable=False, null=True),
        ),
        # 2) Backfill unique values for existing rows.
        migrations.RunPython(populate_uuids, migrations.RunPython.noop),
        # 3) Enforce uniqueness + index now that every row has a value.
        migrations.AlterField(
            model_name='user',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True),
        ),
    ]
