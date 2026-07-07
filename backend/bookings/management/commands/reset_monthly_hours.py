"""Reset every member's free meeting-room hours for the new month.

Free hours do not carry over: on the 1st of each month a member's used-hours
counter returns to 0. Membership.sync_period() already does this lazily on any
access, so this command is a belt-and-braces sweep you can wire to Windows Task
Scheduler (or cron) to run at 00:05 on the 1st.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from bookings.models import Membership


class Command(BaseCommand):
    help = "Zero out each member's used free meeting-room hours for the current month."

    def handle(self, *args, **options):
        period = timezone.localdate().strftime('%Y-%m')
        reset = 0
        for membership in Membership.objects.select_related('plan'):
            if membership.sync_period():
                reset += 1
        self.stdout.write(self.style.SUCCESS(
            f'Free-hour reset for {period}: {reset} membership(s) rolled over.'
        ))
