"""Free hours granted per space in the admin's Customize-package modal.

A ticked space gets its own monthly allowance and its own balance: spending it
must not touch the shared meeting-room pool, and a shortfall in one room must not
block another the member still has hours for.
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase

from .models import Booking, Membership, MembershipPlan, Space

User = get_user_model()


class SpaceHoursTestBase(APITestCase):
    """A member with a shared meeting-room pool and one granted room."""

    def setUp(self):
        self.plan = MembershipPlan.objects.create(name='Test Desk', room_hours=10)
        self.meeting = Space.objects.create(
            key='meeting', name='Meeting Rooms', is_free=True, uses_free_hours=True,
            durations=['hourly', 'fullday'], units=2, capacity=8,
        )
        # A paid room that is NOT flagged uses_free_hours — free only because the
        # admin granted it to this member.
        self.studio = Space.objects.create(
            key='studio', name='Podcast Studio', is_free=False, uses_free_hours=False,
            durations=['hourly'], units=1, hour_price=40, capacity=4,
        )
        self.member = User.objects.create_user(
            email='m@example.com', password='pw12345678', is_approved=True,
        )
        self.membership = Membership.objects.create(
            user=self.member, plan=self.plan,
            hours_period=timezone.localdate().strftime('%Y-%m'),
            space_hours={},
        )
        self.grant({self.studio.id: 4})
        # A weekday: the centre closes at 17:00 on Saturday and all day Sunday,
        # so a fixed offset from today would make these tests pass or fail
        # depending on which day they run.
        day = date.today() + timedelta(days=3)
        while day.weekday() >= 5:
            day += timedelta(days=1)
        self.tomorrow = day
        self.client.force_authenticate(self.member)

    def grant(self, mapping):
        """Set this member's per-space allowances, as the Customize modal would."""
        self.membership.space_hours = {str(k): v for k, v in mapping.items()}
        self.membership.save(update_fields=['space_hours'])

    def book(self, space='meeting', **kwargs):
        payload = {'space': space, 'date': self.tomorrow.isoformat(),
                   'duration': 'hourly', 'start_time': '10:00'}
        payload.update(kwargs)
        return self.client.post('/api/bookings/', payload)

    def left_in(self, space):
        self.membership.refresh_from_db()
        return self.membership.hours_left_in(str(space.id))


class PerSpaceFreeHoursTests(SpaceHoursTestBase):
    def test_granted_space_is_free_even_when_not_flagged(self):
        resp = self.book('studio', hours=2)
        self.assertEqual(resp.status_code, 201, resp.data)
        booking = Booking.objects.get(pk=resp.data['id'])
        self.assertTrue(booking.is_free)
        self.assertIsNone(booking.price)
        self.assertEqual(float(booking.free_hours_used), 2)
        self.assertEqual(booking.free_hours_bucket, str(self.studio.id))

    def test_per_space_hours_do_not_touch_the_shared_pool(self):
        self.book('studio', hours=2)
        self.membership.refresh_from_db()
        self.assertEqual(float(self.membership.room_hours_used), 0)
        self.assertEqual(self.membership.room_hours_left, 10)
        self.assertEqual(self.left_in(self.studio), 2)

    def test_spent_grant_falls_back_to_the_normal_rate(self):
        """A grant is a benefit: spending it must not remove access.

        Before, the room was refused once the free hours ran out, leaving the
        member worse off than if they'd never been granted it.
        """
        self.assertEqual(self.book('studio', hours=4).status_code, 201)
        resp = self.book('studio', hours=1, start_time='15:00')
        self.assertEqual(resp.status_code, 201, resp.data)
        booking = Booking.objects.get(pk=resp.data['id'])
        self.assertFalse(booking.is_free)
        self.assertEqual(float(booking.price), 40)          # the room's hourly rate
        self.assertEqual(float(booking.free_hours_used), 0)
        self.assertEqual(booking.free_hours_bucket, '')
        # ...and the shared meeting-room pool is untouched by any of it.
        self.assertEqual(self.book('meeting', hours=2).status_code, 201)

    def test_a_grant_that_only_partly_covers_a_booking_is_left_alone(self):
        self.assertEqual(self.book('studio', hours=3).status_code, 201)   # 1h left
        resp = self.book('studio', hours=2, start_time='15:00')
        self.assertEqual(resp.status_code, 201, resp.data)
        booking = Booking.objects.get(pk=resp.data['id'])
        self.assertEqual(float(booking.price), 80)
        # The spare hour stays available for a booking it can actually cover.
        self.assertEqual(self.left_in(self.studio), 1)
        r = self.book('studio', hours=1, start_time='17:00')   # last slot before closing
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(self.left_in(self.studio), 0)

    def test_a_free_room_stays_free_once_its_grant_is_spent(self):
        """Granting hours on a room that's free with the plan must not cap it."""
        lounge = Space.objects.create(key='lounge', name='Lounge', is_free=True,
                                      uses_free_hours=False, durations=['hourly'],
                                      units=1, capacity=6)
        self.grant({self.studio.id: 4, lounge.id: 1})
        self.assertEqual(self.book('lounge', hours=1).status_code, 201)
        resp = self.book('lounge', hours=1, start_time='15:00')
        self.assertEqual(resp.status_code, 201, resp.data)
        booking = Booking.objects.get(pk=resp.data['id'])
        self.assertTrue(booking.is_free)
        self.assertIsNone(booking.price)

    def test_the_shared_pool_still_refuses(self):
        """Meeting-room behaviour is deliberately unchanged."""
        self.membership.room_hours_used = 9
        self.membership.save(update_fields=['room_hours_used'])
        resp = self.book('meeting', hours=2)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Not enough free hours', str(resp.data))

    def test_grant_wins_over_the_shared_pool(self):
        """A space that is both flagged and granted draws on its own allowance."""
        self.grant({self.meeting.id: 3})
        resp = self.book('meeting', hours=2)
        self.assertEqual(resp.status_code, 201, resp.data)
        self.membership.refresh_from_db()
        self.assertEqual(float(self.membership.room_hours_used), 0)
        self.assertEqual(self.left_in(self.meeting), 1)

    def test_ungranted_unflagged_space_is_still_paid(self):
        self.grant({})
        resp = self.book('studio', hours=2)
        self.assertEqual(resp.status_code, 201, resp.data)
        booking = Booking.objects.get(pk=resp.data['id'])
        self.assertFalse(booking.is_free)
        self.assertEqual(float(booking.free_hours_used), 0)
        self.assertEqual(float(booking.price), 80)

    def test_cancel_refunds_the_same_bucket(self):
        booking_id = self.book('studio', hours=3).data['id']
        self.assertEqual(self.left_in(self.studio), 1)
        resp = self.client.post(f'/api/bookings/{booking_id}/cancel/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(self.left_in(self.studio), 4)
        self.membership.refresh_from_db()
        self.assertEqual(float(self.membership.room_hours_used), 0)

    def test_cancel_refunds_the_recorded_bucket_after_the_grant_changes(self):
        """Hours go back where they were taken from, not where they'd go now."""
        booking_id = self.book('studio', hours=2).data['id']
        # The admin removes the studio grant while the booking still holds hours.
        self.membership.refresh_from_db()
        self.grant({})
        self.client.post(f'/api/bookings/{booking_id}/cancel/')
        self.membership.refresh_from_db()
        # Refunded to the studio bucket — the shared pool is never credited hours
        # it did not pay for.
        self.assertEqual(float(self.membership.room_hours_used), 0)
        self.assertEqual(
            float((self.membership.space_hours_used or {}).get(str(self.studio.id), 0)), 0)

    def test_month_rollover_clears_per_space_usage(self):
        self.book('studio', hours=3)
        self.membership.refresh_from_db()
        self.membership.hours_period = '2000-01'   # pretend a month has passed
        self.membership.save(update_fields=['hours_period'])
        self.assertEqual(self.membership.hours_left_in(str(self.studio.id)), 4)
        self.membership.refresh_from_db()
        self.assertEqual(self.membership.space_hours_used, {})

    def test_summary_reports_each_grant(self):
        self.book('studio', hours=1)
        self.membership.refresh_from_db()
        rows = self.membership.space_hours_summary
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['name'], 'Podcast Studio')
        self.assertEqual((rows[0]['total'], rows[0]['used'], rows[0]['left']), (4, 1, 3))

    def test_summary_skips_a_deleted_space(self):
        self.grant({self.studio.id: 4, 999999: 2})
        self.assertEqual([r['space'] for r in self.membership.space_hours_summary],
                         [self.studio.id])

    def test_dashboard_exposes_the_balances(self):
        self.book('studio', hours=1)
        resp = self.client.get('/api/overview/')
        self.assertEqual(resp.status_code, 200, resp.data)
        rows = resp.data['stats']['space_hours']
        self.assertEqual([(r['name'], r['left']) for r in rows], [('Podcast Studio', 3)])


class AdminPerSpaceGrantTests(APITestCase):
    """The Customize-package endpoint that writes those grants."""

    def setUp(self):
        self.plan = MembershipPlan.objects.create(name='Test Desk', room_hours=10)
        self.studio = Space.objects.create(
            key='studio', name='Podcast Studio', durations=['hourly'], units=1)
        self.member = User.objects.create_user(
            email='m@example.com', password='pw12345678', is_approved=True)
        self.admin = User.objects.create_user(
            email='a@example.com', password='pw12345678', is_approved=True,
            role=User.Role.ADMIN)
        self.client.force_authenticate(self.admin)

    def set_membership(self, **extra):
        payload = {'plan': self.plan.id, 'custom_plan_name': 'Bespoke'}
        payload.update(extra)
        return self.client.post(
            f'/api/admin/users/{self.member.id}/set-membership/', payload, format='json')

    def test_grant_is_stored_and_returned(self):
        resp = self.set_membership(space_hours={str(self.studio.id): 6})
        self.assertIn(resp.status_code, (200, 201), resp.data)
        self.assertEqual(resp.data['membership']['space_hours'], {str(self.studio.id): 6.0})
        ms = Membership.objects.get(user=self.member)
        self.assertEqual(ms.space_allowance(self.studio.id), 6)

    def test_unknown_space_and_non_positive_hours_are_dropped(self):
        resp = self.set_membership(space_hours={
            str(self.studio.id): 6, '999999': 3, 'abc': 1,
        })
        self.assertEqual(resp.data['membership']['space_hours'], {str(self.studio.id): 6.0})
        # 0 hours would read as "free room, no allowance" and block the space.
        resp = self.set_membership(space_hours={str(self.studio.id): 0})
        self.assertEqual(resp.data['membership']['space_hours'], {})

    def test_removing_a_grant_clears_its_usage(self):
        self.set_membership(space_hours={str(self.studio.id): 6})
        ms = Membership.objects.get(user=self.member)
        ms.consume_hours(str(self.studio.id), 2)
        self.set_membership(space_hours={})
        ms.refresh_from_db()
        self.assertEqual(ms.space_hours, {})
        # Stale usage would silently eat the allowance if the space is re-granted.
        self.assertEqual(ms.space_hours_used, {})


class SharedPoolSupersededTests(SpaceHoursTestBase):
    """The shared meeting-room figure stops being shown once it's superseded."""

    def test_pool_applies_while_a_flagged_space_is_ungranted(self):
        # Meeting Rooms is flagged and not granted -> the shared figure still means something.
        self.assertTrue(self.membership.shared_hours_apply)
        resp = self.client.get('/api/overview/')
        self.assertTrue(resp.data['stats']['shared_hours_apply'])

    def test_pool_is_superseded_once_every_flagged_space_is_granted(self):
        self.grant({self.studio.id: 4, self.meeting.id: 6})
        self.assertFalse(self.membership.shared_hours_apply)
        resp = self.client.get('/api/overview/')
        self.assertFalse(resp.data['stats']['shared_hours_apply'])
        # The hours themselves are untouched — this is display only.
        self.membership.refresh_from_db()
        self.assertEqual(self.membership.effective_hours, 10)

    def test_pool_applies_again_when_a_grant_is_removed(self):
        self.grant({self.meeting.id: 6})
        self.assertFalse(self.membership.shared_hours_apply)
        self.grant({})
        self.assertTrue(self.membership.shared_hours_apply)

    def test_pool_applies_when_the_member_has_no_grants(self):
        """A member who was never customized must see exactly what they saw before.

        Guards the case where no space is flagged uses_free_hours at all: without
        grants there is nothing to supersede the shared figure, so it still shows.
        """
        self.grant({})
        Space.objects.update(uses_free_hours=False)
        self.assertTrue(self.membership.shared_hours_apply)
        resp = self.client.get('/api/overview/')
        self.assertTrue(resp.data['stats']['shared_hours_apply'])


class UncustomizedMemberUnchangedTests(APITestCase):
    """A member nobody has customized must look exactly as they did before.

    The supersession rule is evaluated in two places (the model and the admin
    members serializer); both must treat "no grants" as "nothing to supersede",
    including when no space is flagged uses_free_hours at all.
    """

    def setUp(self):
        self.plan = MembershipPlan.objects.create(name='Test Desk', room_hours=10)
        Space.objects.create(key='office', name='Day Offices', durations=['hourly'], units=1)
        self.member = User.objects.create_user(
            email='plain@example.com', password='pw12345678', is_approved=True)
        Membership.objects.create(
            user=self.member, plan=self.plan,
            hours_period=timezone.localdate().strftime('%Y-%m'))
        self.admin = User.objects.create_user(
            email='a@example.com', password='pw12345678', is_approved=True,
            role=User.Role.ADMIN)
        self.client.force_authenticate(self.admin)

    def row(self):
        return next(u for u in self.client.get('/api/admin/users/').data
                    if u['email'] == self.member.email)

    def test_members_table_keeps_the_shared_hours(self):
        row = self.row()
        self.assertTrue(row['shared_hours_apply'])
        self.assertEqual(row['space_hours'], [])
        self.assertEqual(row['effective_hours'], 10)

    def test_still_kept_when_no_space_uses_free_hours(self):
        Space.objects.update(uses_free_hours=False)
        self.assertTrue(self.row()['shared_hours_apply'])

    def test_clients_endpoint_agrees(self):
        Space.objects.update(uses_free_hours=False)
        row = next(u for u in self.client.get('/api/admin/clients/').data
                   if u['email'] == self.member.email)
        self.assertTrue(row['shared_hours_apply'])
        self.assertIn('10 room hrs', row['perks'])


class CancellationEmailTests(SpaceHoursTestBase):
    """The cancellation email reports the refund that actually happened."""

    def cancel_and_read_mail(self, space, hours):
        from django.core import mail
        booking_id = self.book(space, hours=hours).data['id']
        mail.outbox = []
        resp = self.client.post(f'/api/bookings/{booking_id}/cancel/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(mail.outbox), 1)
        return mail.outbox[0].body

    def test_granted_room_refund_is_reported(self):
        # Podcast Studio is NOT flagged uses_free_hours — the old wording keyed
        # off that flag and stayed silent about hours it had just returned.
        body = self.cancel_and_read_mail('studio', 2)
        self.assertIn('2 free hours for Podcast Studio', body)
        self.assertIn('returned to your balance', body)

    def test_shared_pool_refund_is_reported(self):
        body = self.cancel_and_read_mail('meeting', 1)
        self.assertIn('1 free hour for Meeting Rooms has been returned', body)

    def test_no_refund_is_not_announced(self):
        # A space that's free with the plan but spends no hours: there is nothing
        # to return, so the email must not claim there was.
        Space.objects.create(key='lounge', name='Lounge', is_free=True,
                             uses_free_hours=False, durations=['hourly'],
                             units=1, capacity=6)
        body = self.cancel_and_read_mail('lounge', 1)
        self.assertNotIn('returned to your balance', body)
