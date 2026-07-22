from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from bookings.models import (
    AdminSettings, BlockedSlot, Booking, FAQ, GalleryImage, Membership,
    MembershipPlan, PackageCategory, PromoCode, SiteContent, Space, TourRequest,
)

User = get_user_model()

# Package categories (unlimited; admin-managed). Plans reference these by slug.
CATEGORIES = [
    {'slug': 'private_office', 'name': 'Private Office', 'order': 1,
     'description': 'Lockable, fully serviced offices for teams.'},
    {'slug': 'dedicated_desk', 'name': 'Dedicated Desk', 'order': 2,
     'description': 'Your own permanent desk in a shared studio.'},
    {'slug': 'virtual_office', 'name': 'Virtual Office', 'order': 3,
     'description': 'A prestige business address without the desk.'},
    {'slug': 'membership', 'name': 'Membership', 'order': 4,
     'description': 'Flexible coworking memberships.'},
    {'slug': 'custom', 'name': 'Customized Package', 'order': 5,
     'description': 'Bespoke bundles configured per client.'},
]

# The primary member's plan (Dedicated Desk is the demo member's package).
PLAN = {
    'name': 'Dedicated Desk',
    'category': 'dedicated_desk',
    'description': 'A permanent desk in a light-filled shared studio, yours 24/7.',
    'badge': 'Best Value',
    'price': 349,
    'period': '/mo',
    'featured': True,
    'room_hours': 15,
    'guest_passes': 2,
    'features': [
        'Permanent desk 24/7',
        '15 hrs meeting rooms',
        'Lockable storage',
        'Mailing address',
    ],
    'perk_note': '2 free guest day passes added by Vivid Space.',
    'order': 2,
}

PACKAGES = [
    {'name': 'Hot Desk', 'category': 'membership', 'price': 199, 'period': '/mo', 'featured': False,
     'room_hours': 5, 'guest_passes': 0, 'order': 1,
     'features': ['Unlimited coworking', '5 hrs meeting rooms', 'Coffee & printing']},
    PLAN,
    {'name': 'Private Office', 'category': 'private_office', 'price': 899, 'period': '/mo',
     'featured': False, 'room_hours': 30, 'guest_passes': 4, 'order': 3,
     'features': ['Lockable office', '30 hrs meeting rooms', 'Team of 4', 'Priority booking'],
     'details': {
         'common_benefits': ['24/7 secure access', 'Fibre internet', 'Meeting-room credits',
                             'Cleaning & utilities included', 'Business mailing address'],
         'offices': [
             {'name': 'Office 11B', 'capacity': 4, 'price': 899, 'photos': []},
             {'name': 'Office 12A', 'capacity': 6, 'price': 1190, 'photos': []},
             {'name': 'Corner Suite', 'capacity': 8, 'price': 1650, 'photos': []},
         ],
     }},
    {'name': 'Virtual Office', 'category': 'virtual_office', 'price': 79, 'period': '/mo',
     'featured': False, 'room_hours': 2, 'guest_passes': 0, 'order': 4,
     'features': ['Prestige business address', 'Mail handling & forwarding',
                  'Local business phone number', '2 hrs meeting rooms']},
    {'name': 'Northwind (Custom)', 'category': 'custom', 'price': 0, 'price_label': 'Custom',
     'period': '', 'featured': False, 'room_hours': 0, 'guest_passes': 0, 'order': 5,
     'features': ['5 dedicated seats', 'Free printing', 'Dedicated manager'],
     'details': {'note': 'Bespoke package configured by an administrator.'}},
]

PROMO_CODES = [
    {'code': 'SPRING25', 'campaign': 'Spring Launch', 'sales_rep': 'Dana Ruiz', 'is_active': True},
    {'code': 'PARTNER-NW', 'campaign': 'Northwind Partners', 'sales_rep': 'Sam Idris', 'is_active': True},
]

# Structured business hours consumed by the availability endpoint.
BUSINESS_HOURS = {
    'mon': {'open': '07:00', 'close': '21:00', 'closed': False},
    'tue': {'open': '07:00', 'close': '21:00', 'closed': False},
    'wed': {'open': '07:00', 'close': '21:00', 'closed': False},
    'thu': {'open': '07:00', 'close': '21:00', 'closed': False},
    'fri': {'open': '07:00', 'close': '21:00', 'closed': False},
    'sat': {'open': '09:00', 'close': '17:00', 'closed': False},
    'sun': {'open': '09:00', 'close': '17:00', 'closed': True},
}

SPACES = [
    {'key': 'meeting', 'name': 'Meeting Rooms', 'icon': 'presentation', 'icon_color': '#2E73E0',
     'gradient': 'linear-gradient(135deg,#2E73E0,#6B3DAE)', 'is_free': True, 'uses_free_hours': True,
     'durations': ['hourly', 'fullday'], 'day_price': 260, 'units': 6, 'is_active': True, 'order': 1,
     'description': 'Bright, glass-walled meeting rooms with video conferencing.',
     'capacity': 10, 'size': '22 m²',
     'amenities': ['wifi', '4K display', 'Whiteboard', 'Coffee'],
     'equipment': ['75" screen', 'Logitech Rally camera', 'Conference phone'],
     'rates': [{'label': 'Per hour', 'price': '40'}, {'label': 'Full day', 'price': '260'}]},
    {'key': 'office', 'name': 'Day Offices', 'icon': 'door-closed', 'icon_color': '#C0379A',
     'gradient': 'linear-gradient(135deg,#6B3DAE,#C0379A)', 'is_free': False,
     'durations': ['hourly', 'fullday'], 'day_price': 90, 'units': 12, 'is_active': True, 'order': 2,
     'description': 'Private, lockable offices you can take by the hour or day.',
     'capacity': 4, 'size': '14 m²',
     'amenities': ['wifi', 'Standing desk', 'Lockable door'],
     'equipment': ['Dual monitors', 'Ergonomic chairs'],
     'rates': [{'label': 'Per hour', 'price': '18'}, {'label': 'Full day', 'price': '90'}]},
    {'key': 'cowork', 'name': 'Coworking', 'icon': 'users', 'icon_color': '#F0822E',
     'gradient': 'linear-gradient(135deg,#C0379A,#F0822E)', 'is_free': True,
     'durations': ['fullday'], 'day_price': 29, 'units': 60, 'is_active': True, 'order': 3,
     'description': 'Open coworking floor with hot desks and lounge seating.',
     'capacity': 60, 'size': '320 m²',
     'amenities': ['wifi', 'Coffee', 'Printing', 'Phone booths'],
     'equipment': ['Sit-stand desks', 'Fast Wi-Fi'],
     'rates': [{'label': 'Day pass', 'price': '29'}, {'label': 'Monthly', 'price': '199'}]},
    {'key': 'lounge', 'name': 'Lounge Access', 'icon': 'armchair', 'icon_color': '#1FB9A6',
     'gradient': 'linear-gradient(135deg,#F0822E,#1FB9A6)', 'is_free': False,
     'durations': ['fullday'], 'day_price': 19, 'units': 30, 'is_active': False, 'order': 4,
     'description': 'Casual lounge with soft seating and barista coffee.',
     'capacity': 30, 'size': '80 m²',
     'amenities': ['wifi', 'Barista coffee'], 'equipment': [],
     'rates': [{'label': 'Day pass', 'price': '19'}]},
]

# Public gallery images (uses the frontend's bundled /photos/ assets).
GALLERY_IMAGES = [
    {'image': '/photos/lobby.jpg', 'caption': 'Lobby', 'category': 'Common', 'order': 0},
    {'image': '/photos/open-floor.jpg', 'caption': 'Open floor', 'category': 'Coworking', 'order': 1},
    {'image': '/photos/meeting-room.jpg', 'caption': 'Meeting room', 'category': 'Meeting rooms', 'order': 2},
    {'image': '/photos/lounge.jpg', 'caption': 'Lounge', 'category': 'Lounge', 'order': 3},
    {'image': '/photos/cafe-bar.jpg', 'caption': 'Cafe bar', 'category': 'Common', 'order': 4},
    {'image': '/photos/rooftop.jpg', 'caption': 'Rooftop', 'category': 'Common', 'order': 5},
]

FAQS = [
    {'question': 'What are your opening hours?',
     'answer': 'The center is open Mon–Fri 7am–9pm and weekends 9am–5pm. Members get 24/7 access.',
     'order': 0},
    {'question': 'Do meeting-room hours roll over?',
     'answer': 'No — free monthly meeting-room hours reset on the 1st and do not carry over.',
     'order': 1},
    {'question': 'Can I book a private office for a single day?',
     'answer': 'Yes. Day offices can be booked by the hour or for a full day from the Reservations page.',
     'order': 2},
    {'question': 'How do I get a promo code?',
     'answer': 'Promo codes are shared by our sales team and partners; enter one when you book a tour.',
     'order': 3},
]

CONTACT = {
    'contact_email': 'hello@vividspace.co',
    'phones': ['+1 (212) 555-0100', '+1 (212) 555-0142'],
    'address': '55 Hudson St, New York, NY 10013',
    'maps_url': 'https://maps.google.com/?q=55+Hudson+St+New+York',
}

# Extra approved members shown in the Clients table.
CLIENTS = [
    {'email': 'maya@loopstudio.co', 'first_name': 'Maya', 'last_name': 'Okonkwo',
     'company': 'Loop Studio', 'plan': 'Private Office'},
    {'email': 'priya@northwind.io', 'first_name': 'Priya', 'last_name': 'Nair',
     'company': 'Northwind', 'plan': 'Northwind (Custom)'},
    {'email': 'sara@pixellab.co', 'first_name': 'Sara', 'last_name': 'Lin',
     'company': 'Pixel Lab', 'plan': 'Dedicated Desk'},
    {'email': 'omar@drift.co', 'first_name': 'Omar', 'last_name': 'Said',
     'company': 'Drift', 'plan': 'Hot Desk'},
    {'email': 'lena@foldwork.co', 'first_name': 'Lena', 'last_name': 'Park',
     'company': 'Foldwork', 'plan': 'Dedicated Desk'},
]

SITE_CONTENT = {
    'hero_headline': 'Space to do your vivid best work.',
    'hero_subheading': 'Light-filled desks, private offices, and meeting rooms designed for focus.',
    'gallery': [{'label': x} for x in
                ['Lobby', 'Open floor', 'Meeting room', 'Lounge', 'Cafe bar', 'Rooftop']],
    'services': [
        {'icon': 'wifi', 'name': '1 Gbps Wi-Fi'},
        {'icon': 'coffee', 'name': 'Coffee & refreshments'},
        {'icon': 'printer', 'name': 'Printing & scanning'},
        {'icon': 'concierge-bell', 'name': 'Front-desk reception'},
        {'icon': 'shield-check', 'name': 'Secure 24/7 access'},
    ],
}


class Command(BaseCommand):
    help = 'Seed demo plans, spaces, an admin and a demo member with bookings.'

    @transaction.atomic
    def handle(self, *args, **options):
        # Package categories first — plans reference them by slug.
        categories = {}
        for c in CATEGORIES:
            cat, _ = PackageCategory.objects.update_or_create(slug=c['slug'], defaults=c)
            categories[c['slug']] = cat
        self.stdout.write(self.style.SUCCESS(f'Categories: {", ".join(categories)}'))

        plans = {}
        for p in PACKAGES:
            defaults = {**p, 'category': categories.get(p.get('category'))}
            plan_obj, _ = MembershipPlan.objects.update_or_create(
                name=p['name'], defaults=defaults)
            plans[p['name']] = plan_obj
        plan = plans['Dedicated Desk']
        self.stdout.write(self.style.SUCCESS(f'Packages: {", ".join(plans)}'))

        spaces = {}
        for s in SPACES:
            space, _ = Space.objects.update_or_create(key=s['key'], defaults=s)
            spaces[s['key']] = space
        self.stdout.write(self.style.SUCCESS(f'Spaces: {", ".join(spaces)}'))

        # Admin account
        admin, created = User.objects.get_or_create(
            email='admin@vividspace.co',
            defaults={'first_name': 'Vivid', 'last_name': 'Admin',
                      'role': User.Role.ADMIN, 'is_approved': True,
                      'is_staff': True, 'is_superuser': True},
        )
        admin.set_password('admin1234')
        admin.role = User.Role.ADMIN
        admin.is_approved = True
        admin.is_staff = True
        admin.is_superuser = True
        admin.save()
        self.stdout.write(self.style.SUCCESS('Admin: admin@vividspace.co / admin1234'))

        # Demo member
        member, _ = User.objects.get_or_create(
            email='mohammad@loopstudio.co',
            defaults={'first_name': 'Mohammad', 'last_name': 'Moussa',
                      'company': 'Loop Studio', 'role': User.Role.MEMBER,
                      'is_approved': True},
        )
        member.set_password('demo1234')
        member.is_approved = True
        member.company = 'Loop Studio'
        member.save()

        this_period = date.today().strftime('%Y-%m')
        Membership.objects.update_or_create(
            user=member,
            defaults={'plan': plan, 'status': Membership.Status.ACTIVE,
                      'member_since': date(2024, 1, 15), 'hours_period': this_period,
                      'room_hours_used': 9, 'guest_passes_used': 0},
        )
        self.stdout.write(self.style.SUCCESS('Member: mohammad@loopstudio.co / demo1234'))

        # A pending signup awaiting admin approval (for the admin queue demo).
        pending, _ = User.objects.get_or_create(
            email='casey@northwind.io',
            defaults={'first_name': 'Casey', 'last_name': 'Nguyen',
                      'company': 'Northwind', 'role': User.Role.MEMBER,
                      'is_approved': False},
        )
        pending.set_password('demo1234')
        pending.save()
        self.stdout.write(self.style.SUCCESS('Pending signup: casey@northwind.io'))

        # Demo bookings for the member.
        member.bookings.all().delete()
        today = date.today()
        demo_bookings = [
            dict(space=spaces['meeting'], unit='Aurora', date=today + timedelta(days=1),
                 duration='hourly', start_time=time(10, 0), end_time=time(11, 0),
                 status=Booking.Status.CONFIRMED, is_free=True, price=None),
            dict(space=spaces['office'], unit='11B', date=today + timedelta(days=5),
                 duration='fullday', start_time=None, end_time=None,
                 status=Booking.Status.CONFIRMED, is_free=False, price=90),
            dict(space=spaces['cowork'], unit='Open floor', date=today + timedelta(days=8),
                 duration='fullday', start_time=None, end_time=None,
                 status=Booking.Status.CONFIRMED, is_free=True, price=None),
            dict(space=spaces['meeting'], unit='Cobalt', date=today - timedelta(days=9),
                 duration='hourly', start_time=time(14, 0), end_time=time(16, 0),
                 status=Booking.Status.CONFIRMED, is_free=True, price=None),
            dict(space=spaces['office'], unit='9A', date=today - timedelta(days=16),
                 duration='fullday', start_time=None, end_time=None,
                 status=Booking.Status.CONFIRMED, is_free=False, price=90),
            dict(space=spaces['cowork'], unit='Open floor', date=today - timedelta(days=23),
                 duration='fullday', start_time=None, end_time=None,
                 status=Booking.Status.CANCELLED, is_free=True, price=None),
        ]
        for b in demo_bookings:
            Booking.objects.create(user=member, **b)
        self.stdout.write(self.style.SUCCESS(f'Bookings: {len(demo_bookings)} for the demo member'))

        # Additional approved clients (Clients table + reservations).
        clients = {}
        for c in CLIENTS:
            u, _ = User.objects.get_or_create(
                email=c['email'],
                defaults={'first_name': c['first_name'], 'last_name': c['last_name'],
                          'company': c['company'], 'role': User.Role.MEMBER, 'is_approved': True},
            )
            u.set_password('demo1234')
            u.is_approved = True
            u.company = c['company']
            u.save()
            m_defaults = {'plan': plans[c['plan']], 'status': Membership.Status.ACTIVE,
                          'member_since': date(2024, 6, 1), 'hours_period': this_period}
            # The Northwind (Custom) client carries a bespoke component bundle.
            if c['plan'] == 'Northwind (Custom)':
                m_defaults['custom_components'] = [
                    {'service': 'meeting_hours', 'quantity': 10},
                    {'service': 'office_days', 'quantity': 5},
                    {'service': 'dedicated_desk', 'quantity': 5},
                ]
                m_defaults['monthly_hours'] = 10
            Membership.objects.update_or_create(user=u, defaults=m_defaults)
            clients[c['first_name']] = u
        self.stdout.write(self.style.SUCCESS(f'Clients: {len(clients)} active members'))

        # Two pending sign-ups awaiting approval.
        for em, fn, ln, co in [('casey@northwind.io', 'Casey', 'Nguyen', 'Northwind'),
                               ('tom@beckerco.com', 'Tom', 'Becker', 'Becker & Co')]:
            pend, _ = User.objects.get_or_create(
                email=em, defaults={'first_name': fn, 'last_name': ln, 'company': co,
                                    'role': User.Role.MEMBER, 'is_approved': False})
            pend.set_password('demo1234')
            pend.is_approved = False
            pend.save()
        self.stdout.write(self.style.SUCCESS('Pending signups: casey@northwind.io, tom@beckerco.com'))

        # Demo accounts skip the email-confirmation gate — nothing is actually
        # mailed when seeding, and unverified accounts can't log in.
        User.objects.update(email_verified=True)

        # Reservations across clients (mix of pending / confirmed / paid).
        Booking.objects.filter(user__in=clients.values()).delete()
        client_res = [
            ('Maya', 'meeting', 'Aurora', 0, 'hourly', time(10, 0), time(11, 0), True, False, False, False),
            ('Sara', 'meeting', 'Cobalt', 6, 'hourly', time(14, 0), time(16, 0), True, False, False, False),
            ('Priya', 'cowork', 'Floor', 4, 'fullday', None, None, True, True, False, False),
            ('Omar', 'lounge', '', 7, 'fullday', None, None, False, True, 19, False),
            ('Maya', 'office', '11B', 4, 'fullday', None, None, False, False, 90, True),
            ('Lena', 'office', '9A', 5, 'fullday', None, None, False, False, 90, True),
        ]
        for fn, sk, unit, days, dur, st, et, free, paid, price, pending in client_res:
            Booking.objects.create(
                user=clients[fn], space=spaces[sk], unit=unit,
                date=today + timedelta(days=days), duration=dur, start_time=st, end_time=et,
                status=Booking.Status.CONFIRMED, is_free=free, is_paid=paid,
                price=(price or None), is_pending=pending,
            )
        self.stdout.write(self.style.SUCCESS(f'Reservations: {len(client_res)} across clients'))

        # Promo codes for tour attribution.
        codes = {}
        for pc in PROMO_CODES:
            obj, _ = PromoCode.objects.update_or_create(code=pc['code'], defaults=pc)
            codes[pc['code']] = obj
        self.stdout.write(self.style.SUCCESS(f'Promo codes: {", ".join(codes)}'))

        # A sample Book-a-Tour submission (attributed to a promo code).
        TourRequest.objects.get_or_create(
            email='jordan@brightfox.io',
            defaults={'first_name': 'Jordan', 'last_name': 'Feld', 'phone': '+1 555 0142',
                      'promo_code': codes.get('SPRING25'), 'promo_code_text': 'SPRING25',
                      'status': TourRequest.Status.NEW},
        )
        self.stdout.write(self.style.SUCCESS('Tour request: jordan@brightfox.io'))

        # An example blocked slot (meeting room, next week, afternoon maintenance).
        BlockedSlot.objects.get_or_create(
            space=spaces['meeting'], date=today + timedelta(days=7),
            start_time=time(13, 0), end_time=time(15, 0),
            defaults={'reason': 'AV maintenance'},
        )
        self.stdout.write(self.style.SUCCESS('Blocked slot: meeting room maintenance'))

        # Gallery images (public gallery).
        GalleryImage.objects.all().delete()
        for g in GALLERY_IMAGES:
            GalleryImage.objects.create(**g)
        self.stdout.write(self.style.SUCCESS(f'Gallery: {len(GALLERY_IMAGES)} images'))

        # FAQs.
        FAQ.objects.all().delete()
        for f in FAQS:
            FAQ.objects.create(**f)
        self.stdout.write(self.style.SUCCESS(f'FAQs: {len(FAQS)}'))

        # Site content + admin settings singletons (incl. public contact info).
        SiteContent.objects.update_or_create(pk=1, defaults=SITE_CONTENT)
        AdminSettings.objects.update_or_create(
            pk=1, defaults={'business_hours': BUSINESS_HOURS,
                            'notification_email': 'owner@vividspace.co', **CONTACT},
        )
        self.stdout.write(self.style.SUCCESS('Site content + settings seeded'))

        self.stdout.write(self.style.SUCCESS('Seed complete.'))
