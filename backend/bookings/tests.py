from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from .models import (
    AdminSettings, BlockedSlot, Booking, CustomizationRequest, FAQ, GalleryImage,
    Membership, MembershipPlan, Order, PackageCategory, PromoCode, Space,
)

User = get_user_model()


class BookingTestBase(APITestCase):
    def setUp(self):
        self.plan = MembershipPlan.objects.create(name='Test Desk', room_hours=10)
        self.meeting = Space.objects.create(
            key='meeting', name='Meeting Rooms', is_free=True, uses_free_hours=True,
            durations=['hourly', 'fullday'], units=2, capacity=8,
        )
        self.member = User.objects.create_user(
            email='m@example.com', password='pw12345678', is_approved=True,
        )
        self.membership = Membership.objects.create(
            user=self.member, plan=self.plan,
            hours_period=timezone.localdate().strftime('%Y-%m'),
        )
        self.tomorrow = date.today() + timedelta(days=1)
        self.client.force_authenticate(self.member)

    def book(self, **kwargs):
        payload = {'space': 'meeting', 'date': self.tomorrow.isoformat(),
                   'duration': 'hourly', 'start_time': '10:00'}
        payload.update(kwargs)
        return self.client.post('/api/bookings/', payload)


class FreeHoursTests(BookingTestBase):
    def test_booking_deducts_free_hours(self):
        resp = self.book(hours=2)
        self.assertEqual(resp.status_code, 201, resp.data)
        self.membership.refresh_from_db()
        self.assertEqual(float(self.membership.room_hours_used), 2)
        self.assertEqual(self.membership.room_hours_left, 8)

    def test_cannot_exceed_balance(self):
        self.membership.room_hours_used = 9
        self.membership.save()
        resp = self.book(hours=2, start_time='08:00')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('free meeting-room hours', str(resp.data))

    def test_cancel_refunds_hours(self):
        resp = self.book(hours=3)
        booking_id = resp.data['id']
        self.membership.refresh_from_db()
        self.assertEqual(float(self.membership.room_hours_used), 3)
        cancel = self.client.post(f'/api/bookings/{booking_id}/cancel/')
        self.assertEqual(cancel.status_code, 200)
        self.membership.refresh_from_db()
        self.assertEqual(float(self.membership.room_hours_used), 0)

    def test_monthly_lazy_reset(self):
        self.membership.room_hours_used = 5
        self.membership.hours_period = '2000-01'
        self.membership.save()
        self.assertEqual(self.membership.room_hours_left, 10)
        self.membership.refresh_from_db()
        self.assertEqual(float(self.membership.room_hours_used), 0)


class OverlapTests(BookingTestBase):
    def test_same_unit_double_booking_rejected(self):
        self.assertEqual(self.book(unit='Aurora').status_code, 201)
        resp = self.book(unit='Aurora', start_time='10:30')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('already booked', str(resp.data))

    def test_capacity_limit_rejected(self):
        self.assertEqual(self.book().status_code, 201)
        self.assertEqual(self.book().status_code, 201)
        resp = self.book()
        self.assertEqual(resp.status_code, 400)
        self.assertIn('fully booked', str(resp.data))

    def test_non_overlapping_allowed(self):
        self.assertEqual(self.book(unit='Aurora', start_time='10:00').status_code, 201)
        self.assertEqual(self.book(unit='Aurora', start_time='11:00').status_code, 201)

    def test_blocked_slot_rejected(self):
        BlockedSlot.objects.create(
            space=self.meeting, date=self.tomorrow,
            start_time=time(9, 0), end_time=time(12, 0), reason='Maintenance',
        )
        resp = self.book(start_time='10:00')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Maintenance', str(resp.data))

    def test_arbitrary_unit_cannot_bypass_capacity(self):
        # meeting units=2: distinct made-up unit labels must still hit the ceiling.
        self.assertEqual(self.book(unit='X').status_code, 201)
        self.assertEqual(self.book(unit='Y').status_code, 201)
        resp = self.book(unit='Z')  # third distinct unit on a 2-unit space
        self.assertEqual(resp.status_code, 400)
        self.assertIn('fully booked', str(resp.data))


class PastBookingTests(BookingTestBase):
    def test_past_date_rejected(self):
        yesterday = (timezone.localdate() - timedelta(days=1)).isoformat()
        resp = self.book(date=yesterday)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('future', str(resp.data).lower())

    def test_elapsed_slot_today_rejected(self):
        now = timezone.localtime()
        if now.hour == 0:
            self.skipTest('No earlier slot exists at midnight.')
        resp = self.book(date=timezone.localdate().isoformat(),
                         start_time=f'{now.hour - 1:02d}:00')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('passed', str(resp.data).lower())

    def test_fullday_today_rejected(self):
        resp = self.book(date=timezone.localdate().isoformat(), duration='fullday')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('upcoming', str(resp.data).lower())

    def test_fullday_future_allowed(self):
        resp = self.book(date=self.tomorrow.isoformat(), duration='fullday')
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_hours_past_closing_rejected(self):
        # Default hours close at 18:00; 15:00 + 6h = 21:00 runs past closing.
        resp = self.book(start_time='15:00', hours=6)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('closing', str(resp.data).lower())

    def test_hours_ending_exactly_at_closing_allowed(self):
        resp = self.book(start_time='15:00', hours=3)  # ends 18:00 sharp
        self.assertEqual(resp.status_code, 201, resp.data)


class FulldayUnitTests(BookingTestBase):
    def test_same_unit_fullday_double_booking_rejected(self):
        self.assertEqual(
            self.book(date=self.tomorrow.isoformat(), duration='fullday', unit='Aurora').status_code, 201)
        resp = self.book(date=self.tomorrow.isoformat(), duration='fullday', unit='Aurora')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('already booked', str(resp.data))

    def test_different_unit_fullday_allowed(self):
        self.assertEqual(
            self.book(date=self.tomorrow.isoformat(), duration='fullday', unit='Aurora').status_code, 201)
        self.assertEqual(
            self.book(date=self.tomorrow.isoformat(), duration='fullday', unit='Borealis').status_code, 201)


class AutoApproveTests(APITestCase):
    """The admin's "Auto-approve bookings" switch must actually gate bookings."""

    def setUp(self):
        self.space = Space.objects.create(
            key='room', name='Room', is_free=False, uses_free_hours=False,
            durations=['hourly'], units=1, hour_price=40)
        self.member = User.objects.create_user(
            email='m@example.com', password='pw12345678', is_approved=True)
        self.admin = User.objects.create_user(
            email='a@example.com', password='pw12345678', is_approved=True,
            role=User.Role.ADMIN)
        self.admin_client = APIClient()
        self.admin_client.force_authenticate(self.admin)
        self.client.force_authenticate(self.member)
        self.day = (timezone.localdate() + timedelta(days=1)).isoformat()

    def _set_auto(self, on):
        s = AdminSettings.load()
        s.auto_approve = on
        s.save()

    def book(self, hour='10:00'):
        return self.client.post('/api/bookings/', {
            'space': 'room', 'date': self.day, 'duration': 'hourly',
            'start_time': hour, 'hours': 1}, format='json')

    def test_switch_on_books_immediately(self):
        self._set_auto(True)
        b = Booking.objects.get(pk=self.book().data['id'])
        self.assertFalse(b.is_pending)

    def test_switch_off_holds_booking_for_approval(self):
        self._set_auto(False)
        b = Booking.objects.get(pk=self.book().data['id'])
        self.assertTrue(b.is_pending)
        self.assertEqual(b.reservation_status, 'pending')

    def test_pending_booking_shows_in_the_admin_pending_filter(self):
        self._set_auto(False)
        self.book()
        rows = self.admin_client.get('/api/admin/reservations/?filter=pending').data
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]['pending'])

    def test_pending_booking_is_not_emailed_as_confirmed(self):
        """Promising a slot that an admin might still reject would be a lie."""
        self._set_auto(False)
        mail.outbox = []
        self.book()
        body = mail.outbox[0].body
        self.assertIn('awaiting confirmation', body)
        self.assertNotIn('Your booking is confirmed', body)
        self.assertIn('request received', mail.outbox[0].subject.lower())

    def test_auto_approved_booking_is_emailed_as_confirmed(self):
        self._set_auto(True)
        mail.outbox = []
        self.book()
        self.assertIn('Your booking is confirmed', mail.outbox[0].body)
        self.assertIn('confirmed', mail.outbox[0].subject.lower())

    def test_admin_approval_confirms_and_emails_the_member(self):
        self._set_auto(False)
        b = Booking.objects.get(pk=self.book().data['id'])
        mail.outbox = []
        resp = self.admin_client.post(f'/api/admin/reservations/{b.id}/approve/')
        self.assertEqual(resp.status_code, 200, resp.data)
        b.refresh_from_db()
        self.assertFalse(b.is_pending)
        # The member was told "awaiting confirmation" — they must hear the outcome.
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['m@example.com'])
        self.assertIn('Your booking is confirmed', mail.outbox[0].body)

    def test_approving_an_already_live_booking_does_not_re_email(self):
        self._set_auto(True)
        b = Booking.objects.get(pk=self.book().data['id'])
        mail.outbox = []
        self.admin_client.post(f'/api/admin/reservations/{b.id}/approve/')
        self.assertEqual(len(mail.outbox), 0)


class SameDayRuleTests(APITestCase):
    """The "Allow same-day bookings" switch and its cutoff must gate today."""

    def setUp(self):
        self.space = Space.objects.create(
            key='room', name='Room', is_free=False, uses_free_hours=False,
            durations=['hourly', 'fullday'], units=1, hour_price=40, day_price=200)
        self.member = User.objects.create_user(
            email='m@example.com', password='pw12345678', is_approved=True)
        self.client.force_authenticate(self.member)
        self.now = timezone.localtime()

    def _rules(self, allow, cutoff=''):
        s = AdminSettings.load()
        s.allow_sameday = allow
        s.sameday_cutoff = cutoff
        s.auto_approve = True
        s.save()

    def _book_today(self):
        if self.now.hour >= 17:
            self.skipTest('No future slot left today.')
        return self.client.post('/api/bookings/', {
            'space': 'room', 'date': timezone.localdate().isoformat(),
            'duration': 'hourly', 'start_time': f'{self.now.hour + 1:02d}:00',
            'hours': 1}, format='json')

    def _book_tomorrow(self):
        return self.client.post('/api/bookings/', {
            'space': 'room', 'date': (timezone.localdate() + timedelta(days=1)).isoformat(),
            'duration': 'hourly', 'start_time': '10:00', 'hours': 1}, format='json')

    def test_switch_on_allows_today(self):
        self._rules(True)
        self.assertEqual(self._book_today().status_code, 201)

    def test_switch_off_refuses_today(self):
        self._rules(False)
        r = self._book_today()
        self.assertEqual(r.status_code, 400)
        self.assertIn('same-day', str(r.data).lower())

    def test_switch_off_still_allows_a_later_date(self):
        """The switch gates today only — it must not block normal bookings."""
        self._rules(False)
        self.assertEqual(self._book_tomorrow().status_code, 201)

    def test_cutoff_already_passed_refuses_today(self):
        # A cutoff of 00:01 is in the past for any run after midnight.
        self._rules(True, cutoff='00:01')
        r = self._book_today()
        self.assertEqual(r.status_code, 400)
        self.assertIn('00:01', str(r.data))

    def test_cutoff_not_yet_reached_allows_today(self):
        self._rules(True, cutoff='23:59')
        self.assertEqual(self._book_today().status_code, 201)

    def test_cutoff_does_not_affect_later_dates(self):
        self._rules(True, cutoff='00:01')
        self.assertEqual(self._book_tomorrow().status_code, 201)

    def test_blank_cutoff_means_no_cutoff(self):
        self._rules(True, cutoff='')
        self.assertEqual(self._book_today().status_code, 201)


class PayAtCenterTests(APITestCase):
    """The "Allow paying at the center" switch must gate the direct booking path
    for priced bookings only."""

    def setUp(self):
        self.paid = Space.objects.create(
            key='paid', name='Paid Room', is_free=False, uses_free_hours=False,
            durations=['hourly'], units=1, hour_price=40)
        self.free = Space.objects.create(
            key='freeroom', name='Free Room', is_free=True, uses_free_hours=False,
            durations=['hourly'], units=1)
        self.member = User.objects.create_user(
            email='m@example.com', password='pw12345678', is_approved=True)
        self.client.force_authenticate(self.member)
        self.day = (timezone.localdate() + timedelta(days=1)).isoformat()
        s = AdminSettings.load()
        s.auto_approve = True
        s.whish_enabled = True
        s.whish_number = '+961 70 000 000'
        s.save()

    def _set_pac(self, on):
        s = AdminSettings.load()
        s.pay_at_center = on
        s.save()

    def _book(self, key, hour='10:00'):
        return self.client.post('/api/bookings/', {
            'space': key, 'date': self.day, 'duration': 'hourly',
            'start_time': hour, 'hours': 1}, format='json')

    def test_switch_on_allows_paying_at_center(self):
        self._set_pac(True)
        self.assertEqual(self._book('paid').status_code, 201)

    def test_switch_off_refuses_a_priced_direct_booking(self):
        self._set_pac(False)
        r = self._book('paid')
        self.assertEqual(r.status_code, 400)
        self.assertIn('paid online', str(r.data))

    def test_switch_off_still_allows_a_free_space(self):
        """The switch is about money — a free space has none to take."""
        self._set_pac(False)
        self.assertEqual(self._book('freeroom').status_code, 201)

    def test_switch_off_still_allows_the_online_order_path(self):
        """Whish *is* the online payment — it must not block itself."""
        self._set_pac(False)
        r = self.client.post('/api/orders/', {'payment_method': 'whish', 'bookings': [
            {'space': 'paid', 'date': self.day, 'duration': 'hourly',
             'start_time': '12:00', 'hours': 1}]}, format='json')
        self.assertEqual(r.status_code, 201, r.data)

    def test_switch_off_still_allows_a_plan_covered_booking(self):
        """Covered by the member's free hours = nothing payable."""
        plan = MembershipPlan.objects.create(name='P', room_hours=10)
        Membership.objects.create(user=self.member, plan=plan,
                                  hours_period=timezone.localdate().strftime('%Y-%m'))
        room = Space.objects.create(
            key='meet', name='Meet', is_free=False, uses_free_hours=True,
            durations=['hourly'], units=1, hour_price=40)
        self._set_pac(False)
        self.assertEqual(self._book('meet').status_code, 201, room.key)

    def test_site_payload_exposes_the_switch(self):
        self._set_pac(False)
        self.assertIs(self.client.get('/api/site/').data['payments']['pay_at_center'], False)


class UnitLabelTests(APITestCase):
    """Every unit of a space must be reachable, and no booking may stay ambiguous
    once the space has more than one unit."""

    def _space(self, **kw):
        opts = dict(key='room', name='Room', is_free=False, uses_free_hours=False,
                    durations=['hourly', 'fullday'], units=1, hour_price=40, day_price=200)
        opts.update(kw)
        return Space.objects.create(**opts)

    def test_unnamed_units_get_padded_so_all_are_bookable(self):
        # 2 rooms but only one named: the second must still be pickable.
        s = self._space(units=2, unit_names=['1A'])
        self.assertEqual(s.unit_labels, ['1A', 'Room 2'])

    def test_auto_labels_are_named_after_the_space(self):
        s = self._space(name='Dedicated Desk', units=3)
        self.assertEqual(s.unit_labels,
                         ['Dedicated Desk 1', 'Dedicated Desk 2', 'Dedicated Desk 3'])

    def test_auto_labels_fall_back_when_space_has_no_name(self):
        self.assertEqual(self._space(name='', units=2).unit_labels, ['Unit 1', 'Unit 2'])

    def test_padding_never_duplicates_an_admin_name(self):
        # Naming a room literally "Room 2" must not make the auto label collide:
        # position 2 is taken, so the pad skips ahead rather than repeating it.
        s = self._space(units=2, unit_names=['Room 2'])
        self.assertEqual(s.unit_labels, ['Room 2', 'Room 3'])
        self.assertEqual(len(set(s.unit_labels)), 2)

    def test_labels_capped_at_unit_count(self):
        s = self._space(units=2, unit_names=['a', 'b', 'c'])
        self.assertEqual(s.unit_labels, ['a', 'b'])


class UnitBackfillTests(APITestCase):
    """Bookings made while a space had one unit carry unit='' — once the space
    grows they must be stamped, or they can be double-booked (a named booking on
    the same physical room is accepted because the blank one names nothing)."""

    def setUp(self):
        self.space = Space.objects.create(
            key='meet', name='Meeting Room', is_free=False, uses_free_hours=False,
            durations=['hourly'], units=1, hour_price=40)
        self.member = User.objects.create_user(
            email='m@example.com', password='pw12345678', is_approved=True)
        self.admin = User.objects.create_user(
            email='a@example.com', password='pw12345678', is_approved=True,
            role=User.Role.ADMIN)
        self.admin_client = APIClient()
        self.admin_client.force_authenticate(self.admin)
        self.client.force_authenticate(self.member)
        self.day = timezone.localdate() + timedelta(days=1)

    def _legacy(self, hour=10):
        """A booking from when the space had a single unit — no unit recorded."""
        return Booking.objects.create(
            user=self.member, space=self.space, date=self.day,
            duration=Booking.Duration.HOURLY, start_time=time(hour, 0),
            end_time=time(hour + 1, 0), is_free=False, price=40)

    def test_backfill_stamps_unitless_bookings_when_space_grows(self):
        b = self._legacy()
        self.assertEqual(b.unit, '')
        self.space.units = 2
        self.space.save()
        self.assertEqual(self.space.assign_missing_units(), 1)
        b.refresh_from_db()
        self.assertEqual(b.unit, 'Meeting Room 1')

    def test_backfill_gives_overlapping_bookings_different_units(self):
        a, b = self._legacy(), self._legacy()          # same hour, both blank
        self.space.units = 2
        self.space.save()
        self.space.assign_missing_units()
        a.refresh_from_db(); b.refresh_from_db()
        self.assertNotEqual(a.unit, b.unit)
        self.assertEqual({a.unit, b.unit}, {'Meeting Room 1', 'Meeting Room 2'})

    def test_backfill_leaves_non_overlapping_bookings_on_the_same_unit(self):
        a, b = self._legacy(hour=10), self._legacy(hour=14)   # no clash
        self.space.units = 2
        self.space.save()
        self.space.assign_missing_units()
        a.refresh_from_db(); b.refresh_from_db()
        self.assertEqual(a.unit, 'Meeting Room 1')
        self.assertEqual(b.unit, 'Meeting Room 1')

    def test_admin_raising_units_backfills_automatically(self):
        """The whole point: after the admin adds a unit, the legacy booking's room
        is claimed, so booking that same room at that hour is refused."""
        self._legacy()
        resp = self.admin_client.patch(
            f'/api/admin/spaces/{self.space.id}/', {'units': 2}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        clash = self.client.post('/api/bookings/', {
            'space': 'meet', 'date': self.day.isoformat(), 'duration': 'hourly',
            'start_time': '10:00', 'hours': 1, 'unit': 'Meeting Room 1'}, format='json')
        self.assertEqual(clash.status_code, 400, clash.data)
        self.assertIn('already booked', str(clash.data))
        # The genuinely free second room is still bookable.
        ok = self.client.post('/api/bookings/', {
            'space': 'meet', 'date': self.day.isoformat(), 'duration': 'hourly',
            'start_time': '10:00', 'hours': 1, 'unit': 'Meeting Room 2'}, format='json')
        self.assertEqual(ok.status_code, 201, ok.data)


class BookingExperienceTests(BookingTestBase):
    def test_attendees_over_capacity_rejected(self):
        resp = self.book(attendees=20)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('holds up to', str(resp.data))

    def test_booking_disabled_space_rejected(self):
        self.meeting.booking_enabled = False
        self.meeting.save()
        resp = self.book()
        self.assertEqual(resp.status_code, 400)
        self.assertIn('not available', str(resp.data))

    def test_temporarily_unavailable_space_rejected(self):
        self.meeting.admin_status = Space.AdminStatus.TEMPORARILY_UNAVAILABLE
        self.meeting.save()
        resp = self.book()
        self.assertEqual(resp.status_code, 400)
        self.assertIn('not available', str(resp.data))

    def test_booking_emails_client_and_owner(self):
        # This covers the confirmed-booking email, so opt in explicitly rather
        # than leaning on the auto-approve default.
        s = AdminSettings.load()
        s.auto_approve = True
        s.save()
        mail.outbox = []
        resp = self.book(attendees=4)
        self.assertEqual(resp.status_code, 201, resp.data)
        # Two emails: confirmation to the client + notification to the owner.
        self.assertEqual(len(mail.outbox), 2)
        recipients = [addr for m in mail.outbox for addr in m.to]
        self.assertIn('m@example.com', recipients)  # client confirmation
        client_mail = next(m for m in mail.outbox if m.to == ['m@example.com'])
        owner_mail = next(m for m in mail.outbox if m.to != ['m@example.com'])
        self.assertIn('confirmed', client_mail.subject.lower())
        self.assertIn('New booking', owner_mail.subject)

    def test_whish_order_also_notifies_the_owner(self):
        """The online-payment path bypasses BookingViewSet, so it has to send the
        owner notification itself — otherwise Whish bookings arrive silently."""
        mail.outbox = []
        paid = Space.objects.create(
            key='studio', name='Studio', is_free=False, uses_free_hours=False,
            durations=['hourly'], units=1, hour_price=40)
        resp = self.client.post('/api/orders/', {'payment_method': 'whish', 'bookings': [
            {'space': paid.key, 'date': self.tomorrow.isoformat(), 'duration': 'hourly',
             'start_time': '15:00', 'hours': 1}]}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        owner_mails = [m for m in mail.outbox if m.to != ['m@example.com']]
        self.assertEqual(len(owner_mails), 1)
        self.assertIn('New booking', owner_mails[0].subject)
        # An online order must not be reported as cash owed at the center.
        body = owner_mails[0].body
        self.assertIn('Whish online', body)
        self.assertIn('ORD-', body)
        self.assertNotIn('Pay at center', body)


class ChangeRequestTests(BookingTestBase):
    """Member reschedule request → admin approve / reject flow."""

    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_user(
            email='a@example.com', password='pw12345678', is_approved=True,
            role=User.Role.ADMIN,
        )
        self.admin_client = APIClient()
        self.admin_client.force_authenticate(self.admin)
        self.day_after = self.tomorrow + timedelta(days=1)
        # A confirmed hourly booking (tomorrow 10:00–11:00) to reschedule.
        resp = self.book(hours=1)
        self.assertEqual(resp.status_code, 201, resp.data)
        self.booking_id = resp.data['id']

    def request_change(self, **kw):
        payload = {'date': self.day_after.isoformat(), 'start_time': '14:00'}
        payload.update(kw)
        return self.client.post(f'/api/bookings/{self.booking_id}/request-change/', payload)

    def approve(self):
        return self.admin_client.post(f'/api/admin/reservations/{self.booking_id}/approve-change/')

    def reject(self):
        return self.admin_client.post(f'/api/admin/reservations/{self.booking_id}/reject-change/')

    # ---- request ----

    def test_request_locks_booking_and_emails_owner(self):
        mail.outbox = []
        resp = self.request_change()
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['change_requested'])
        self.assertEqual(resp.data['requested']['time'], '14:00')
        b = Booking.objects.get(pk=self.booking_id)
        self.assertTrue(b.change_requested)
        self.assertEqual(b.requested_date, self.day_after)
        self.assertEqual(b.requested_start_time, time(14, 0))
        # Original booking is untouched until the admin decides.
        self.assertEqual(b.date, self.tomorrow)
        self.assertEqual(b.start_time, time(10, 0))
        # Owner is notified (single email, not to the member).
        self.assertEqual(len(mail.outbox), 1)
        self.assertNotIn('m@example.com', mail.outbox[0].to)
        self.assertIn('change request', mail.outbox[0].subject.lower())
        # The email must point at a menu that actually exists in the admin panel.
        self.assertIn('Daily Bookings → Change requests', mail.outbox[0].body)

    def test_locked_booking_cannot_be_cancelled(self):
        self.request_change()
        resp = self.client.post(f'/api/bookings/{self.booking_id}/cancel/')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('awaiting review', str(resp.data))
        self.assertFalse(Booking.objects.get(pk=self.booking_id).is_cancelled)

    def test_cannot_request_change_twice(self):
        self.assertEqual(self.request_change().status_code, 200)
        resp = self.request_change(start_time='15:00')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('already', str(resp.data).lower())

    def test_request_rejects_past_date(self):
        resp = self.request_change(date=(date.today() - timedelta(days=1)).isoformat())
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(Booking.objects.get(pk=self.booking_id).change_requested)

    def test_request_rejects_blocked_slot(self):
        BlockedSlot.objects.create(
            space=self.meeting, date=self.day_after,
            start_time=time(13, 0), end_time=time(15, 0), reason='Maintenance',
        )
        resp = self.request_change()
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Maintenance', str(resp.data))
        self.assertFalse(Booking.objects.get(pk=self.booking_id).change_requested)

    def test_other_member_cannot_request_change(self):
        other = User.objects.create_user(
            email='o@example.com', password='pw12345678', is_approved=True,
        )
        other_client = APIClient()
        other_client.force_authenticate(other)
        resp = other_client.post(
            f'/api/bookings/{self.booking_id}/request-change/',
            {'date': self.day_after.isoformat(), 'start_time': '14:00'},
        )
        self.assertEqual(resp.status_code, 404)

    # ---- admin decision ----

    def test_admin_approve_applies_change_and_emails_member(self):
        self.request_change()
        mail.outbox = []
        resp = self.approve()
        self.assertEqual(resp.status_code, 200, resp.data)
        b = Booking.objects.get(pk=self.booking_id)
        self.assertEqual(b.date, self.day_after)
        self.assertEqual(b.start_time, time(14, 0))
        self.assertEqual(b.end_time, time(15, 0))       # 1hr length preserved
        self.assertFalse(b.change_requested)
        self.assertIsNone(b.requested_date)
        self.assertIsNone(b.requested_start_time)
        self.assertEqual(mail.outbox[-1].to, ['m@example.com'])
        self.assertIn('rescheduled', mail.outbox[-1].subject.lower())

    def test_admin_reject_keeps_original_and_emails_member(self):
        self.request_change()
        mail.outbox = []
        resp = self.reject()
        self.assertEqual(resp.status_code, 200, resp.data)
        b = Booking.objects.get(pk=self.booking_id)
        self.assertEqual(b.date, self.tomorrow)         # unchanged
        self.assertEqual(b.start_time, time(10, 0))
        self.assertFalse(b.change_requested)
        self.assertIsNone(b.requested_date)
        self.assertEqual(mail.outbox[-1].to, ['m@example.com'])
        self.assertIn('declined', mail.outbox[-1].subject.lower())

    def test_approve_revalidates_availability(self):
        self.request_change()
        # The requested slot gets blocked after the request but before approval.
        BlockedSlot.objects.create(
            space=self.meeting, date=self.day_after,
            start_time=time(13, 0), end_time=time(15, 0), reason='Maintenance',
        )
        resp = self.approve()
        self.assertEqual(resp.status_code, 400)
        b = Booking.objects.get(pk=self.booking_id)
        # Still locked and unchanged so the admin can retry / reject.
        self.assertTrue(b.change_requested)
        self.assertEqual(b.date, self.tomorrow)

    def test_change_filter_lists_request(self):
        self.request_change()
        resp = self.admin_client.get('/api/admin/reservations/?filter=change')
        self.assertEqual(resp.status_code, 200)
        row = next(r for r in resp.data if r['id'] == self.booking_id)
        self.assertTrue(row['change_requested'])
        self.assertEqual(row['status'], 'change')
        self.assertIn('14:00', row['requested_label'])

    def test_approve_without_request_is_rejected(self):
        resp = self.approve()
        self.assertEqual(resp.status_code, 400)
        self.assertIn('no pending change', str(resp.data).lower())

    # ---- reschedule may also change hours / duration ----

    def test_reschedule_changes_hours_and_resettles_free_hours(self):
        # Booked 1 free hour in setUp → 1 used, 9 left.
        self.assertEqual(self.request_change(hours=3).status_code, 200)
        b = Booking.objects.get(pk=self.booking_id)
        self.assertEqual(b.requested_hours, 3)
        self.assertEqual(self.approve().status_code, 200)
        b.refresh_from_db()
        self.assertEqual(b.start_time, time(14, 0))
        self.assertEqual(b.end_time, time(17, 0))          # 3-hour window
        self.assertEqual(float(b.free_hours_used), 3)
        self.membership.refresh_from_db()
        self.assertEqual(float(self.membership.room_hours_used), 3)  # 1 refunded, 3 taken

    def test_reschedule_hourly_to_fullday_refunds_hours(self):
        self.assertEqual(
            self.request_change(duration='fullday').status_code, 200)
        self.assertEqual(self.approve().status_code, 200)
        b = Booking.objects.get(pk=self.booking_id)
        self.assertEqual(b.duration, Booking.Duration.FULLDAY)
        self.assertIsNone(b.start_time)
        self.assertEqual(float(b.free_hours_used), 0)
        self.membership.refresh_from_db()
        self.assertEqual(float(self.membership.room_hours_used), 0)  # hour returned

    def test_reschedule_to_fullday_today_rejected(self):
        resp = self.request_change(date=timezone.localdate().isoformat(), duration='fullday')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('upcoming', str(resp.data).lower())

    def test_approve_blocked_when_not_enough_free_hours(self):
        # Drain the balance so the requested longer booking can't be covered.
        self.membership.room_hours_used = 9   # effective left = 1 (+1 held by booking)
        self.membership.save()
        # 09:00 + 5h = 14:00, within closing; the shortfall is the free-hours balance.
        self.assertEqual(self.request_change(start_time='09:00', hours=5).status_code, 200)
        resp = self.approve()
        self.assertEqual(resp.status_code, 400)
        self.assertIn('free meeting-room hours', str(resp.data))
        b = Booking.objects.get(pk=self.booking_id)
        self.assertTrue(b.change_requested)       # rolled back, still pending
        self.assertEqual(b.date, self.tomorrow)


class SpacePricingVisibilityTests(APITestCase):
    """Rates are members-only: hiding them in the UI isn't enough if the public
    payload still carries the numbers."""

    def setUp(self):
        self.paid = Space.objects.create(
            key='office', name='Day Office', durations=['fullday', 'hourly'], units=1,
            is_free=False, day_price=90, hour_price=18,
            rates=[{'label': 'Full day', 'price': '90'}],
        )
        self.free = Space.objects.create(
            key='meeting', name='Meeting Room', durations=['hourly'], units=1,
            is_free=True, uses_free_hours=True,
        )
        self.member = User.objects.create_user(
            email='u@example.com', password='pw12345678', is_approved=True)

    def _get(self, key):
        return self.client.get(f'/api/spaces/{key}/').data

    def test_anonymous_visitor_gets_no_prices(self):
        d = self._get('office')
        self.assertIsNone(d['day_price'])
        self.assertIsNone(d['hour_price'])
        self.assertEqual(d['rates'], [])

    def test_anonymous_payload_does_not_contain_the_numbers_anywhere(self):
        """Guards against a price leaking through some other field."""
        body = str(self.client.get('/api/spaces/').data)
        self.assertNotIn('90', body)
        self.assertNotIn('18', body)

    def test_signed_in_member_sees_prices(self):
        self.client.force_authenticate(self.member)
        d = self._get('office')
        self.assertEqual(float(d['day_price']), 90)
        self.assertEqual(float(d['hour_price']), 18)
        self.assertEqual(d['rates'], [{'label': 'Full day', 'price': '90'}])

    def test_free_space_still_advertises_itself_when_logged_out(self):
        # "Free with plan" is a selling point, not a rate — it must survive.
        d = self._get('meeting')
        self.assertTrue(d['free'])
        self.assertEqual(d['meta'], 'Free with plan')

    def test_non_price_detail_still_public(self):
        d = self._get('office')
        self.assertEqual(d['name'], 'Day Office')
        self.assertEqual(d['durations'], ['fullday', 'hourly'])


class SpaceAvailabilityTests(APITestCase):
    def setUp(self):
        self.space = Space.objects.create(
            key='office', name='Day Office', durations=['fullday'], units=1, capacity=4,
        )
        self.user = User.objects.create_user(
            email='u@example.com', password='pw12345678', is_approved=True,
        )
        self.today = date.today()

    def test_public_list_and_detail(self):
        resp = self.client.get('/api/spaces/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data[0]['availability_status'], 'available')
        detail = self.client.get('/api/spaces/office/')
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data['capacity'], 4)

    def test_status_temporarily_unavailable(self):
        self.space.admin_status = Space.AdminStatus.TEMPORARILY_UNAVAILABLE
        self.space.save()
        self.assertEqual(self.space.availability_status(), 'temporarily_unavailable')

    def test_status_blocked(self):
        BlockedSlot.objects.create(space=self.space, date=self.today)  # full-day block
        self.assertEqual(self.space.availability_status(self.today), 'blocked')

    def test_status_fully_booked(self):
        Booking.objects.create(user=self.user, space=self.space, date=self.today,
                               duration='fullday')
        self.assertEqual(self.space.availability_status(self.today), 'fully_booked')

    def test_filter_min_capacity(self):
        Space.objects.create(key='pod', name='Phone Pod', units=1, capacity=1)
        resp = self.client.get('/api/spaces/?min_capacity=3')
        keys = [s['key'] for s in resp.data]
        self.assertIn('office', keys)
        self.assertNotIn('pod', keys)


class PublicContentTests(APITestCase):
    def test_categories_and_package_filter(self):
        po = PackageCategory.objects.create(name='Private Office', slug='private_office')
        PackageCategory.objects.create(name='Virtual Office', slug='virtual_office')
        MembershipPlan.objects.create(name='PO Plan', category=po)
        cats = self.client.get('/api/categories/')
        self.assertEqual(cats.status_code, 200)
        self.assertEqual(len(cats.data), 2)
        pkgs = self.client.get('/api/packages/?category=private_office')
        self.assertEqual([p['name'] for p in pkgs.data], ['PO Plan'])
        self.assertEqual(pkgs.data[0]['category']['slug'], 'private_office')

    def test_hidden_and_archived_packages_excluded(self):
        MembershipPlan.objects.create(name='Hidden', is_visible=False)
        MembershipPlan.objects.create(name='Archived', is_archived=True)
        MembershipPlan.objects.create(name='Live')
        names = [p['name'] for p in self.client.get('/api/packages/').data]
        self.assertEqual(names, ['Live'])

    def test_public_gallery_and_faqs(self):
        GalleryImage.objects.create(image='/x.jpg', caption='A', order=1)
        GalleryImage.objects.create(image='/y.jpg', caption='B', order=0, is_visible=False)
        FAQ.objects.create(question='Q?', answer='A', order=0)
        gallery = self.client.get('/api/gallery/')
        self.assertEqual([g['caption'] for g in gallery.data], ['A'])  # hidden excluded
        faqs = self.client.get('/api/faqs/')
        self.assertEqual(len(faqs.data), 1)

    def test_site_config(self):
        resp = self.client.get('/api/site/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('contact', resp.data)
        self.assertIn('business_hours', resp.data)


class AdminManagementTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email='a@example.com', password='pw12345678', is_approved=True,
            role=User.Role.ADMIN,
        )
        self.client.force_authenticate(self.admin)

    def test_package_duplicate_and_archive(self):
        plan = MembershipPlan.objects.create(name='Base', price=100)
        dup = self.client.post(f'/api/admin/packages/{plan.id}/duplicate/')
        self.assertEqual(dup.status_code, 201)
        self.assertEqual(dup.data['name'], 'Base (copy)')
        arch = self.client.post(f'/api/admin/packages/{plan.id}/toggle-archive/')
        self.assertTrue(arch.data['is_archived'])
        # Archived excluded from default admin list, shown with include_archived.
        default = self.client.get('/api/admin/packages/')
        self.assertNotIn('Base', [p['name'] for p in default.data])
        incl = self.client.get('/api/admin/packages/?include_archived=1')
        self.assertIn('Base', [p['name'] for p in incl.data])

    def test_gallery_reorder(self):
        a = GalleryImage.objects.create(image='/a.jpg', order=0)
        b = GalleryImage.objects.create(image='/b.jpg', order=1)
        resp = self.client.post('/api/admin/gallery/reorder/',
                                [{'id': a.id, 'order': 5}, {'id': b.id, 'order': 0}],
                                format='json')
        self.assertEqual(resp.status_code, 200)
        a.refresh_from_db(); b.refresh_from_db()
        self.assertEqual((a.order, b.order), (5, 0))

    def test_faq_and_category_crud(self):
        faq = self.client.post('/api/admin/faqs/', {'question': 'Q?', 'answer': 'A'})
        self.assertEqual(faq.status_code, 201)
        cat = self.client.post('/api/admin/categories/', {'name': 'Studios'})
        self.assertEqual(cat.status_code, 201)
        self.assertEqual(cat.data['slug'], 'studios')  # auto-slugged


class CustomizationRequestTests(APITestCase):
    """Public 'build your own package' enquiry, incl. per-office time of day."""

    def setUp(self):
        self.tomorrow = (date.today() + timedelta(days=1)).isoformat()
        self.day2 = (date.today() + timedelta(days=2)).isoformat()

    def submit(self, items):
        return self.client.post('/api/customize/', {
            'name': 'Jane Doe', 'email': 'jane@example.com', 'phone': '+123',
            'items': items,
        }, format='json')

    def test_persists_fullday_and_hourly_timing(self):
        mail.outbox = []
        resp = self.submit([
            {'office': 'Private Office', 'dates': [self.tomorrow, self.day2]},  # defaults to full day
            {'office': 'Meeting Room', 'dates': [self.tomorrow],
             'duration': 'hourly', 'start_time': '14:00', 'hours': 2},
        ])
        self.assertEqual(resp.status_code, 201, resp.data)
        cr = CustomizationRequest.objects.get(email='jane@example.com')
        office = next(i for i in cr.items if i['office'] == 'Private Office')
        room = next(i for i in cr.items if i['office'] == 'Meeting Room')
        self.assertEqual(office['duration'], 'fullday')
        self.assertEqual(room['duration'], 'hourly')
        self.assertEqual(room['start_time'], '14:00')
        self.assertEqual(room['hours'], 2)
        # Owner email carries the timing.
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('14:00', mail.outbox[0].body)
        self.assertIn('Full day', mail.outbox[0].body)

    def test_hourly_requires_start_time(self):
        resp = self.submit([
            {'office': 'Meeting Room', 'dates': [self.tomorrow], 'duration': 'hourly'},
        ])
        self.assertEqual(resp.status_code, 400)
        self.assertIn('start time', str(resp.data).lower())

    def test_rejects_out_of_range_hours(self):
        resp = self.submit([
            {'office': 'Meeting Room', 'dates': [self.tomorrow],
             'duration': 'hourly', 'start_time': '09:00', 'hours': 20},
        ])
        self.assertEqual(resp.status_code, 400)


class ScheduleChangeTests(APITestCase):
    """Member proposes a package-schedule edit → admin approve / reject flow."""

    def setUp(self):
        self.plan = MembershipPlan.objects.create(name='Office', room_hours=5, price=100)
        self.member = User.objects.create_user(
            email='m@example.com', password='pw12345678', is_approved=True,
        )
        self.tomorrow = (date.today() + timedelta(days=1)).isoformat()
        self.day2 = (date.today() + timedelta(days=2)).isoformat()
        # A bespoke membership: one dated package, one editable-but-empty package,
        # and one fixed lifetime package.
        self.membership = Membership.objects.create(
            user=self.member, plan=self.plan, custom_plan_name='Bespoke',
            hours_period=timezone.localdate().strftime('%Y-%m'),
            custom_components=[
                {'name': 'Private Office', 'plan': self.plan.id, 'dates': [self.tomorrow]},
                {'name': 'Desk', 'plan': self.plan.id, 'dates': []},
                {'name': 'Lounge', 'lifetime': True, 'dates': []},
            ],
        )
        self.admin = User.objects.create_user(
            email='a@example.com', password='pw12345678', is_approved=True,
            role=User.Role.ADMIN,
        )
        self.member_client = APIClient()
        self.member_client.force_authenticate(self.member)
        self.admin_client = APIClient()
        self.admin_client.force_authenticate(self.admin)

    def request_change(self, components):
        return self.member_client.post(
            '/api/schedule-change/', {'components': components}, format='json')

    def approve(self):
        return self.admin_client.post(
            f'/api/admin/users/{self.member.id}/approve-schedule-change/')

    def reject(self):
        return self.admin_client.post(
            f'/api/admin/users/{self.member.id}/reject-schedule-change/')

    @staticmethod
    def _comp(components, name):
        return next((c for c in components if c.get('name') == name), None)

    # ---- request ----

    def test_request_stores_pending_and_emails_owner(self):
        mail.outbox = []
        resp = self.request_change([{'name': 'Private Office', 'dates': [self.tomorrow, self.day2]}])
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertTrue(resp.data['schedule_change_requested'])
        self.membership.refresh_from_db()
        self.assertTrue(self.membership.schedule_change_requested)
        # Live schedule is untouched until approval (Private Office still 1 day).
        self.assertEqual(self._comp(self.membership.custom_components, 'Private Office')['dates'],
                         [self.tomorrow])
        # Proposal captures the new days and preserves the fixed lifetime package.
        pending = self.membership.pending_components
        self.assertEqual(self._comp(pending, 'Private Office')['dates'], [self.tomorrow, self.day2])
        self.assertTrue(self._comp(pending, 'Lounge')['lifetime'])
        self.assertEqual(len(mail.outbox), 1)
        self.assertNotIn('m@example.com', mail.outbox[0].to)
        self.assertIn('schedule change', mail.outbox[0].subject.lower())

    def test_cannot_request_twice(self):
        self.assertEqual(self.request_change([{'name': 'Private Office', 'dates': [self.tomorrow]}]).status_code, 200)
        resp = self.request_change([{'name': 'Private Office', 'dates': [self.day2]}])
        self.assertEqual(resp.status_code, 400)
        self.assertIn('already', str(resp.data).lower())

    def test_rejects_unknown_package(self):
        resp = self.request_change([{'name': 'Penthouse', 'dates': [self.tomorrow]}])
        self.assertEqual(resp.status_code, 400)
        self.assertIn('part of your package', str(resp.data))
        self.membership.refresh_from_db()
        self.assertFalse(self.membership.schedule_change_requested)

    def test_rejects_new_past_date(self):
        past = (date.today() - timedelta(days=1)).isoformat()
        resp = self.request_change([{'name': 'Private Office', 'dates': [past]}])
        self.assertEqual(resp.status_code, 400)
        self.assertIn('past', str(resp.data).lower())

    def test_carryover_past_dates_allowed(self):
        # A day already in the member's schedule that has since fallen into the
        # past must carry through untouched — not block the whole submission.
        past = (date.today() - timedelta(days=3)).isoformat()
        self.membership.custom_components[0]['dates'] = [past, self.tomorrow]
        self.membership.save()
        resp = self.request_change([{'name': 'Private Office', 'dates': [past, self.tomorrow, self.day2]}])
        self.assertEqual(resp.status_code, 200, resp.data)
        self.membership.refresh_from_db()
        kept = self._comp(self.membership.pending_components, 'Private Office')['dates']
        self.assertIn(past, kept)          # history preserved
        self.assertIn(self.day2, kept)     # new future day added

    def test_rejects_same_day_two_packages(self):
        resp = self.request_change([
            {'name': 'Private Office', 'dates': [self.tomorrow]},
            {'name': 'Desk', 'dates': [self.tomorrow]},
        ])
        self.assertEqual(resp.status_code, 400)
        self.assertIn('only one package', str(resp.data))

    def test_no_editable_schedule(self):
        plain = User.objects.create_user(
            email='p@example.com', password='pw12345678', is_approved=True)
        Membership.objects.create(user=plain, plan=self.plan, custom_components=[])
        c = APIClient()
        c.force_authenticate(plain)
        resp = c.post('/api/schedule-change/', {'components': []}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('no editable schedule', str(resp.data).lower())

    def test_requires_membership(self):
        nomem = User.objects.create_user(
            email='n@example.com', password='pw12345678', is_approved=True)
        c = APIClient()
        c.force_authenticate(nomem)
        resp = c.post('/api/schedule-change/', {'components': []}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('membership', str(resp.data).lower())

    # ---- admin decision ----

    def test_admin_approve_applies_and_emails_member(self):
        self.request_change([{'name': 'Private Office', 'dates': [self.tomorrow, self.day2]}])
        mail.outbox = []
        resp = self.approve()
        self.assertEqual(resp.status_code, 200, resp.data)
        self.membership.refresh_from_db()
        self.assertFalse(self.membership.schedule_change_requested)
        self.assertIsNone(self.membership.pending_components)
        self.assertEqual(self._comp(self.membership.custom_components, 'Private Office')['dates'],
                         [self.tomorrow, self.day2])
        self.assertTrue(self._comp(self.membership.custom_components, 'Lounge')['lifetime'])
        self.assertEqual(mail.outbox[-1].to, ['m@example.com'])
        self.assertIn('schedule', mail.outbox[-1].subject.lower())

    def test_admin_reject_keeps_original_and_emails_member(self):
        self.request_change([{'name': 'Private Office', 'dates': [self.day2]}])
        mail.outbox = []
        resp = self.reject()
        self.assertEqual(resp.status_code, 200, resp.data)
        self.membership.refresh_from_db()
        self.assertFalse(self.membership.schedule_change_requested)
        self.assertIsNone(self.membership.pending_components)
        # Original schedule preserved (Private Office still just tomorrow).
        self.assertEqual(self._comp(self.membership.custom_components, 'Private Office')['dates'],
                         [self.tomorrow])
        self.assertEqual(mail.outbox[-1].to, ['m@example.com'])
        self.assertIn('declined', mail.outbox[-1].subject.lower())

    def test_approve_without_request_rejected(self):
        resp = self.approve()
        self.assertEqual(resp.status_code, 400)
        self.assertIn('no pending schedule change', str(resp.data).lower())

    def test_admin_user_list_flags_change(self):
        self.request_change([{'name': 'Private Office', 'dates': [self.tomorrow, self.day2]}])
        resp = self.admin_client.get('/api/admin/users/')
        row = next(u for u in resp.data if u['id'] == self.member.id)
        self.assertTrue(row['schedule_change_requested'])
        self.assertEqual(row['schedule_change_days'], 2)


class WhishOrderTests(APITestCase):
    """Pay-with-Whish checkout: place order → held bookings → verify/reject."""

    def setUp(self):
        s = AdminSettings.load()
        s.whish_enabled = True
        s.whish_number = '+961 70 123 456'
        s.save()
        self.space = Space.objects.create(
            key='paidroom', name='Paid Room', is_free=False, uses_free_hours=False,
            durations=['hourly', 'fullday'], units=1, hour_price=50, day_price=200,
        )
        self.member = User.objects.create_user(
            email='p@example.com', password='pw12345678', is_approved=True)
        self.admin = User.objects.create_user(
            email='adm@example.com', password='pw12345678', is_approved=True,
            role=User.Role.ADMIN)
        self.admin_client = APIClient()
        self.admin_client.force_authenticate(self.admin)
        self.client.force_authenticate(self.member)
        self.tomorrow = (timezone.localdate() + timedelta(days=1)).isoformat()

    def place(self, **kw):
        item = {'space': 'paidroom', 'date': self.tomorrow, 'duration': 'hourly',
                'start_time': '10:00', 'hours': 2}
        item.update(kw)
        return self.client.post('/api/orders/', {'payment_method': 'whish', 'bookings': [item]}, format='json')

    def test_order_creates_pending_booking_with_number(self):
        resp = self.place()
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(resp.data['order_number'].startswith('ORD-'))
        self.assertEqual(resp.data['status'], 'awaiting_payment')
        self.assertEqual(float(resp.data['amount']), 100.0)      # 50/hr * 2
        self.assertEqual(resp.data['whish']['number'], '+961 70 123 456')
        self.assertEqual(resp.data['whish']['message'], resp.data['order_number'])
        order = Order.objects.get(order_number=resp.data['order_number'])
        b = order.bookings.get()
        self.assertTrue(b.is_pending)
        self.assertFalse(b.is_paid)

    def test_owner_can_fetch_order_but_not_others(self):
        num = self.place().data['order_number']
        self.assertEqual(self.client.get(f'/api/orders/{num}/').status_code, 200)
        other = APIClient()
        other.force_authenticate(User.objects.create_user(
            email='x@example.com', password='pw12345678', is_approved=True))
        self.assertEqual(other.get(f'/api/orders/{num}/').status_code, 404)

    def test_mark_paid_confirms_bookings(self):
        num = self.place().data['order_number']
        order = Order.objects.get(order_number=num)
        resp = self.admin_client.post(f'/api/admin/orders/{order.id}/mark-paid/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['status'], 'paid')
        b = order.bookings.get()
        b.refresh_from_db()
        self.assertTrue(b.is_paid)
        self.assertFalse(b.is_pending)

    def _revenue(self):
        kpis = self.admin_client.get('/api/admin/dashboard/').data['kpis']
        return next(k['value'] for k in kpis if k['label'] == 'Revenue this month')

    def test_revenue_counts_paid_orders_not_unpaid_ones(self):
        """Revenue comes from Payments: an order only counts once it's marked paid."""
        self.assertEqual(self._revenue(), '$0')
        order = Order.objects.get(order_number=self.place().data['order_number'])
        self.assertEqual(self._revenue(), '$0')          # awaiting payment — not revenue yet
        self.admin_client.post(f'/api/admin/orders/{order.id}/mark-paid/')
        self.assertEqual(self._revenue(), '$100')        # 50/hr * 2

    def test_revenue_includes_center_paid_booking_with_no_order(self):
        """Pay-at-center bookings never get an Order, so they're counted via the
        order-less leg — otherwise that income would vanish from the KPI."""
        b = Booking.objects.create(
            user=self.member, space=self.space, date=timezone.localdate(),
            duration=Booking.Duration.FULLDAY, is_free=False, price=200, is_paid=True)
        self.assertIsNone(b.order)
        self.assertEqual(self._revenue(), '$200')

    def test_revenue_is_cash_basis_not_booking_date(self):
        """Money counts toward the month it was collected, even when the booking
        it paid for falls in a later month."""
        next_month = (timezone.localdate().replace(day=1) + timedelta(days=32)).replace(day=1)
        order = Order.objects.get(
            order_number=self.place(date=next_month.isoformat()).data['order_number'])
        self.admin_client.post(f'/api/admin/orders/{order.id}/mark-paid/')
        # Booking is next month; the payment landed today — so it's this month's revenue.
        self.assertEqual(order.bookings.get().date.month, next_month.month)
        self.assertEqual(self._revenue(), '$100')

    def test_revenue_does_not_double_count_an_orders_bookings(self):
        """The order leg and the order-less leg must stay disjoint."""
        order = Order.objects.get(order_number=self.place().data['order_number'])
        self.admin_client.post(f'/api/admin/orders/{order.id}/mark-paid/')
        # The booking under the order is now is_paid — it must not also be summed.
        self.assertEqual(self._revenue(), '$100')

    def _receipt(self, num):
        """Upload a 1x1 PNG as the transfer receipt."""
        png = (b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
               b'\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00'
               b'\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82')
        return self.client.post(
            f'/api/orders/{num}/receipt/',
            {'file': SimpleUploadedFile('r.png', png, content_type='image/png')},
            format='multipart')

    def _auto(self, on):
        s = AdminSettings.load()
        s.auto_approve = on
        s.save()

    def test_receipt_confirms_the_booking_without_an_admin_click(self):
        self._auto(True)
        num = self.place().data['order_number']
        order = Order.objects.get(order_number=num)
        self.assertTrue(order.bookings.get().is_pending)   # held until the receipt
        mail.outbox = []
        self.assertEqual(self._receipt(num).status_code, 200)
        b = order.bookings.get()
        b.refresh_from_db()
        self.assertFalse(b.is_pending)                      # no Approve click needed
        self.assertIn('Your booking is confirmed', mail.outbox[0].body)

    def test_receipt_does_not_mark_the_money_paid(self):
        """The upload proves a file is an image, not that a transfer happened —
        an admin still verifies it, and only then does it count as revenue."""
        self._auto(True)
        num = self.place().data['order_number']
        self._receipt(num)
        order = Order.objects.get(order_number=num)
        self.assertEqual(order.status, Order.Status.SUBMITTED)   # still awaiting review
        self.assertFalse(order.bookings.get().is_paid)
        self.assertEqual(self._revenue(), '$0')

    def test_marking_paid_after_a_receipt_does_not_re_email(self):
        self._auto(True)
        num = self.place().data['order_number']
        self._receipt(num)
        order = Order.objects.get(order_number=num)
        mail.outbox = []
        self.admin_client.post(f'/api/admin/orders/{order.id}/mark-paid/')
        self.assertEqual(len(mail.outbox), 0)   # already told them it's confirmed
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PAID)
        self.assertEqual(self._revenue(), '$100')

    def test_receipt_respects_auto_approve_being_off(self):
        """Off means the admin vets every booking — a receipt can't override that."""
        self._auto(False)
        num = self.place().data['order_number']
        mail.outbox = []
        self._receipt(num)
        self.assertTrue(Order.objects.get(order_number=num).bookings.get().is_pending)
        self.assertEqual(len(mail.outbox), 0)

    def test_reject_cancels_bookings_and_frees_slot(self):
        num = self.place().data['order_number']
        order = Order.objects.get(order_number=num)
        resp = self.admin_client.post(f'/api/admin/orders/{order.id}/reject/', {'reason': 'No transfer found'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['status'], 'rejected')
        self.assertTrue(order.bookings.get().status == Booking.Status.CANCELLED)
        # Slot is free again — a fresh hourly booking at the same time succeeds.
        again = self.place()
        self.assertEqual(again.status_code, 201, again.data)

    def test_mark_paid_on_rejected_order_blocked(self):
        num = self.place().data['order_number']
        order = Order.objects.get(order_number=num)
        self.admin_client.post(f'/api/admin/orders/{order.id}/reject/', {'reason': 'x'})
        resp = self.admin_client.post(f'/api/admin/orders/{order.id}/mark-paid/')
        self.assertEqual(resp.status_code, 400)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.REJECTED)  # not flipped to paid

    def test_duplicate_lines_in_one_order_rejected(self):
        item = {'space': 'paidroom', 'date': self.tomorrow, 'duration': 'hourly',
                'start_time': '10:00', 'hours': 2}
        resp = self.client.post('/api/orders/',
                                {'payment_method': 'whish', 'bookings': [item, dict(item)]},
                                format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)  # rolled back

    def test_admin_export_orders_xlsx(self):
        self.place()
        resp = self.admin_client.get('/api/admin/orders/export/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('spreadsheet', resp['Content-Type'])
        self.assertIn('attachment', resp['Content-Disposition'])

    def test_admin_export_reservations_xlsx(self):
        self.place()
        resp = self.admin_client.get('/api/admin/reservations/export/')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('spreadsheet', resp['Content-Type'])
        # The download is named for what the admin sees, not the legacy route.
        self.assertIn('daily-bookings', resp['Content-Disposition'])
        self.assertNotIn('reservations', resp['Content-Disposition'])
