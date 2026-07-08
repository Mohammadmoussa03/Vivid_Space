from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from .models import (
    BlockedSlot, Booking, CustomizationRequest, FAQ, GalleryImage, Membership,
    MembershipPlan, PackageCategory, PromoCode, Space,
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


class BookingExperienceTests(BookingTestBase):
    def test_attendees_over_capacity_rejected(self):
        resp = self.book(attendees=20)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('holds up to', str(resp.data))

    def test_booking_emails_client_and_owner(self):
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
