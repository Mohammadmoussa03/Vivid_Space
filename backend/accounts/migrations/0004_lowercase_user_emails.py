"""Canonicalise every stored email to lowercase.

Email is the login credential and Postgres compares it case-sensitively, so a
row written as "John@X.com" could never be signed into once the app started
normalising input. New writes are normalised by `User.save()`; this backfills
the rows that predate it.

Collisions (two accounts differing only in case) can't both be lowercased —
the column is unique. The oldest account in such a group wins and the others
are left exactly as they are, so nothing is silently merged or lost.
"""
from django.db import migrations


def lowercase_emails(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    # Rows that are already canonical own their lowercase form.
    claimed = {
        email for email in User.objects.values_list('email', flat=True)
        if email and email == email.strip().lower()
    }

    # Oldest first, so the original account keeps the canonical address.
    for user in User.objects.exclude(email='').order_by('date_joined', 'pk'):
        target = (user.email or '').strip().lower()
        if target == user.email:
            continue
        if target in claimed:
            continue  # would collide with an existing account — leave untouched
        user.email = target
        user.save(update_fields=['email'])
        claimed.add(target)


def noop(apps, schema_editor):
    """Irreversible by design — the original casing isn't recorded anywhere."""


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_user_email_verified'),
    ]

    operations = [
        migrations.RunPython(lowercase_emails, noop),
    ]
