"""Turn sameday_cutoff into a real "HH:MM" time (blank = no cutoff).

The field was a 60-char free-text column defaulting to the sentence
"No cutoff — allow any time", while the admin form asked for HH:MM — it could
never hold what its own label requested, and nothing read it either way. It now
stores the same "HH:MM" shape as business_hours.

Existing values that aren't HH:MM are cleared to blank ("no cutoff"), which is
what the old default meant. This has to run *before* the column shrinks to 5
chars, or the old sentence would be too long for the new type.
"""
import re

from django.db import migrations, models

HHMM = re.compile(r'^([01]\d|2[0-3]):[0-5]\d$')


def clear_non_time_values(apps, schema_editor):
    AdminSettings = apps.get_model('bookings', 'AdminSettings')
    for row in AdminSettings.objects.all():
        value = (row.sameday_cutoff or '').strip()
        if not HHMM.match(value):
            # Prose like "No cutoff — allow any time" means exactly that: no cutoff.
            row.sameday_cutoff = ''
            row.save(update_fields=['sameday_cutoff'])


def noop(apps, schema_editor):
    """Nothing to restore — the old text carried no setting anyone read."""


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0022_sitecontent_about_body_sitecontent_about_eyebrow_and_more'),
    ]

    operations = [
        migrations.RunPython(clear_non_time_values, noop),
        migrations.AlterField(
            model_name='adminsettings',
            name='sameday_cutoff',
            field=models.CharField(blank=True, default='', max_length=5),
        ),
    ]
