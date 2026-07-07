from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.utils import timezone
from rest_framework.test import APITestCase

from .models import (
    BlockedSlot, Booking, FAQ, GalleryImage, Membership, MembershipPlan,
    PackageCategory, PromoCode, Space,
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
