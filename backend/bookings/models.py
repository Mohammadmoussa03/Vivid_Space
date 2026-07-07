from datetime import date

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class PackageCategory(models.Model):
    """An admin-managed package family (unlimited; e.g. Private Office, Membership)."""

    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=90, unique=True, blank=True)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)
    is_visible = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'name']
        verbose_name = 'Package category'
        verbose_name_plural = 'Package categories'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug and self.name:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class MembershipPlan(models.Model):
    """A purchasable membership tier / package (e.g. Dedicated Desk)."""

    name = models.CharField(max_length=80, unique=True)
    # Which admin-managed package family this plan belongs to (unlimited categories).
    category = models.ForeignKey(
        PackageCategory, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='plans',
    )
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    # Free-form price display, e.g. "Custom" for bespoke packages. Falls back to price.
    price_label = models.CharField(max_length=40, blank=True)
    period = models.CharField(max_length=20, default='/mo', blank=True)
    featured = models.BooleanField(default=False)
    # Optional promotional badge, e.g. "Best Value" (in addition to `featured`).
    badge = models.CharField(max_length=40, blank=True)
    room_hours = models.PositiveIntegerField(default=0)
    guest_passes = models.PositiveIntegerField(default=0)
    # List of strings shown under "Included in your plan" / package perks.
    features = models.JSONField(default=list, blank=True)
    # Uploaded image URLs (see /api/admin/upload/) and an optional video URL/embed.
    images = models.JSONField(default=list, blank=True)
    video_url = models.CharField(max_length=300, blank=True)
    # Free-form category-specific content. For Private Office this holds the list
    # of offices, e.g. {"offices": [{"name", "capacity", "photos": [...], "price"}],
    # "common_benefits": [...]}. Other categories may use it for extra copy/media.
    details = models.JSONField(default=dict, blank=True)
    perk_note = models.CharField(max_length=240, blank=True)
    is_active = models.BooleanField(default=True)
    # Whether booking is enabled for this package, and whether it shows publicly.
    booking_enabled = models.BooleanField(default=True)
    is_visible = models.BooleanField(default=True)
    is_archived = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'price']

    def __str__(self):
        return self.name

    @property
    def member_count(self):
        return self.memberships.count()

    @property
    def display_price(self):
        if self.price_label:
            return self.price_label
        return f'${int(self.price)}' if self.price == self.price.to_integral_value() else f'${self.price}'


class Membership(models.Model):
    """Links a user to their active plan and tracks usage."""

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        PAUSED = 'paused', 'Paused'
        CANCELLED = 'cancelled', 'Cancelled'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='membership'
    )
    plan = models.ForeignKey(
        MembershipPlan, on_delete=models.PROTECT, related_name='memberships'
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    member_since = models.DateField(default=date.today)
    room_hours_used = models.DecimalField(max_digits=6, decimal_places=1, default=0)
    guest_passes_used = models.PositiveIntegerField(default=0)
    # Per-client override of the plan's monthly free meeting-room hours. When null
    # the plan's own room_hours applies. Set by an admin for bespoke arrangements.
    monthly_hours = models.PositiveIntegerField(null=True, blank=True)
    # The YYYY-MM period the current room_hours_used belongs to. Used by
    # sync_period() to zero usage on the 1st of a new month (hours don't carry over).
    hours_period = models.CharField(max_length=7, blank=True)
    # Line items for a Customized Package, e.g.
    # [{"service": "meeting_hours", "quantity": 2}, {"service": "office_days", "quantity": 2}].
    # Only meaningful when plan.category == CUSTOM; configured by an admin.
    custom_components = models.JSONField(default=list, blank=True)
    # Per-client price override for a bespoke arrangement. When null the plan's
    # own price applies. `custom_price_label` allows a free-form display such as
    # "Custom" or "Negotiated" and takes precedence over the numeric value.
    custom_price = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    custom_price_label = models.CharField(max_length=60, blank=True)
    # A bespoke package name the admin chose for this member. When set it is shown
    # instead of the base plan's name; the `plan` FK still supplies included perks.
    custom_plan_name = models.CharField(max_length=120, blank=True)

    def __str__(self):
        return f'{self.user.email} · {self.display_name}'

    @property
    def display_name(self):
        """The package name shown for this member: custom name, else the plan's."""
        return self.custom_plan_name or self.plan.name

    @property
    def effective_price(self):
        """The price this member actually pays: per-client override, else the plan's."""
        return self.custom_price if self.custom_price is not None else self.plan.price

    @property
    def price_display(self):
        """Human-readable price: custom label, else custom/plan amount."""
        if self.custom_price_label:
            return self.custom_price_label
        price = self.effective_price or 0
        return f'${int(price)}' if price == int(price) else f'${price}'

    @property
    def is_custom(self):
        """Whether this membership carries any bespoke overrides."""
        return bool(self.custom_plan_name or self.custom_components
                    or self.custom_price is not None or self.custom_price_label
                    or self.monthly_hours is not None)

    @property
    def effective_hours(self):
        """Monthly free meeting-room hours: per-client override, else the plan's."""
        return self.monthly_hours if self.monthly_hours is not None else self.plan.room_hours

    def sync_period(self):
        """Reset used hours to 0 when the calendar month has rolled over.

        Lazy monthly reset so balances are correct even if no scheduler runs the
        reset_monthly_hours command. Returns True if a reset happened.
        """
        period = timezone.localdate().strftime('%Y-%m')
        if self.hours_period != period:
            self.hours_period = period
            self.room_hours_used = 0
            if self.pk:
                self.save(update_fields=['hours_period', 'room_hours_used'])
            return True
        return False

    @property
    def room_hours_left(self):
        self.sync_period()
        return max(0, float(self.effective_hours) - float(self.room_hours_used))

    @property
    def guest_passes_left(self):
        return max(0, self.plan.guest_passes - self.guest_passes_used)


class Space(models.Model):
    """A bookable space type (meeting room, day office, coworking, lounge)."""

    class Duration(models.TextChoices):
        HOURLY = 'hourly', 'Hourly'
        FULLDAY = 'fullday', 'Full day'

    class AdminStatus(models.TextChoices):
        AVAILABLE = 'available', 'Available'
        TEMPORARILY_UNAVAILABLE = 'temporarily_unavailable', 'Temporarily unavailable'

    key = models.SlugField(max_length=20, unique=True)
    name = models.CharField(max_length=80)
    icon = models.CharField(max_length=40, default='door-closed')
    icon_color = models.CharField(max_length=9, default='#2E73E0')
    # Gradient used on the admin space cards.
    gradient = models.CharField(max_length=120, blank=True)
    # Rich workspace-page content.
    description = models.TextField(blank=True)
    capacity = models.PositiveIntegerField(null=True, blank=True)
    size = models.CharField(max_length=40, blank=True)  # e.g. "25 m²"
    amenities = models.JSONField(default=list, blank=True)
    equipment = models.JSONField(default=list, blank=True)
    # Uploaded image URLs and an optional video URL/embed for the workspace page.
    images = models.JSONField(default=list, blank=True)
    video_url = models.CharField(max_length=300, blank=True)
    # Whether this space is free with a plan or paid at the center.
    is_free = models.BooleanField(default=True)
    # Whether hourly bookings of this space draw down a member's monthly free
    # meeting-room hours (True for the meeting room). Admin-configurable.
    uses_free_hours = models.BooleanField(default=False)
    # Allowed durations, e.g. ["hourly", "fullday"].
    durations = models.JSONField(default=list, blank=True)
    # A space can be booked by the day and/or by the hour; the admin sets each rate.
    day_price = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    hour_price = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    # Number of bookable units of this space (rooms / desks).
    units = models.PositiveIntegerField(default=1)
    # Editable rate rows shown in admin, e.g. [{"label": "Per hour", "price": "40"}].
    rates = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    # Whether visitors can book this space, and an admin availability override.
    booking_enabled = models.BooleanField(default=True)
    admin_status = models.CharField(
        max_length=24, choices=AdminStatus.choices, default=AdminStatus.AVAILABLE
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return self.name

    @property
    def meta(self):
        return 'Free with plan' if self.is_free else 'Pay at center'

    def availability_status(self, day=None):
        """Coarse availability badge for a given day (defaults to today):
        `temporarily_unavailable`, `blocked`, `fully_booked`, or `available`."""
        day = day or timezone.localdate()
        if (not self.is_active or not self.booking_enabled
                or self.admin_status == self.AdminStatus.TEMPORARILY_UNAVAILABLE):
            return 'temporarily_unavailable'
        day_blocks = BlockedSlot.objects.filter(date=day).filter(
            models.Q(space=self) | models.Q(space__isnull=True)
        )
        if any(b.start_time is None or b.end_time is None for b in day_blocks):
            return 'blocked'
        booked = self.bookings.filter(date=day).exclude(
            status=Booking.Status.CANCELLED
        ).count()
        if booked >= (self.units or 1):
            return 'fully_booked'
        return 'available'


class Booking(models.Model):
    """A member's reservation of a space."""

    class Duration(models.TextChoices):
        HOURLY = 'hourly', 'Hourly'
        FULLDAY = 'fullday', 'Full day'

    class Status(models.TextChoices):
        CONFIRMED = 'confirmed', 'Confirmed'
        CANCELLED = 'cancelled', 'Cancelled'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bookings'
    )
    space = models.ForeignKey(Space, on_delete=models.PROTECT, related_name='bookings')
    # Optional room/desk label, e.g. "Aurora" or "11B".
    unit = models.CharField(max_length=60, blank=True)

    date = models.DateField()
    duration = models.CharField(max_length=10, choices=Duration.choices, default=Duration.HOURLY)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    # Number of attendees (for spaces where it applies, e.g. meeting rooms).
    attendees = models.PositiveIntegerField(null=True, blank=True)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.CONFIRMED)
    # New reservations from the public site may await admin approval.
    is_pending = models.BooleanField(default=False)
    # Whether this booking was free with the plan (snapshot of the space at booking time).
    is_free = models.BooleanField(default=True)
    # Free meeting-room hours drawn down by this booking (for exact refund on cancel).
    free_hours_used = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    price = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    # Payment settled at the center (only meaningful for paid bookings).
    is_paid = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-start_time', '-id']

    def __str__(self):
        return f'{self.user.email} · {self.space.name} · {self.date}'

    @property
    def is_cancelled(self):
        return self.status == self.Status.CANCELLED

    @property
    def is_past(self):
        return not self.is_cancelled and self.date < date.today()

    @property
    def when(self):
        """Bucket used by the frontend's Upcoming / Past / Cancelled filter."""
        if self.is_cancelled:
            return 'cancelled'
        return 'past' if self.is_past else 'upcoming'

    @property
    def status_label(self):
        return {'cancelled': 'Cancelled', 'past': 'Completed', 'upcoming': 'Upcoming'}[self.when]

    @property
    def reservation_status(self):
        """Status bucket used by the admin reservations table."""
        if self.is_cancelled:
            return 'cancelled'
        if self.is_pending:
            return 'pending'
        return 'completed' if self.is_past else 'confirmed'


# ---- Default page content for the (editable) SiteContent singleton ----
# These make the whole public site data-driven while keeping the shipped design.

def _default_intro():
    return ('Our workspaces build connection, belonging, and an excitement to be part of '
            'something bigger. All in an atmosphere that looks after people, and makes them '
            'feel excited about coming in. Even on a Monday.')


def _default_stats():
    return [
        {'value': 500, 'suffix': '+', 'label': 'Members'},
        {'value': 12, 'suffix': 'k+', 'label': 'Hours booked'},
        {'value': 4.9, 'suffix': '/5', 'label': 'Member rating'},
        {'value': 98, 'suffix': '%', 'label': 'Would recommend'},
    ]


def _default_solutions():
    return {
        'eyebrow': 'Solutions',
        'title': 'Room to grow into',
        'items': [
            {'tag': 'Offices', 'title': 'Private & team offices',
             'body': 'Lockable, move-in-ready offices sized for one to fifty. Branded to feel like yours, backed by the whole building.',
             'cta': 'Explore offices'},
            {'tag': 'Coworking', 'title': 'Desks & memberships',
             'body': 'Hot desks and dedicated desks on light-filled floors, with unlimited coffee and a community that shows up.',
             'cta': 'See coworking'},
            {'tag': 'Meetings & Events', 'title': 'Rooms that make you look good',
             'body': 'Polished meeting rooms and event spaces with the AV, catering and calm you need to run the day.',
             'cta': 'Book a room'},
        ],
    }


def _default_hero_cards():
    return {
        'badges': [
            {'icon': '⭐', 'value': '4.9/5', 'caption': 'Rated by Members'},
            {'icon': '📍', 'value': 'Beirut', 'caption': 'Premium Workspace'},
        ],
        'pills': ['24/7 Access', 'Private Offices', 'Meeting Rooms'],
    }


def _default_footer():
    return {
        'note': 'Premium flexible workspaces that foster genuine community and human connection in vibrant city locations.',
        'columns': [
            {'title': 'Solutions', 'links': ['Private offices', 'Coworking', 'Meeting rooms', 'Virtual office']},
            {'title': 'Company', 'links': ['About', 'Careers', 'Blog', 'Contact']},
            {'title': 'Support', 'links': ['Help centre', 'Book a tour', 'Members', 'Community']},
        ],
    }


def _default_headings():
    return {
        'packages': {'eyebrow': 'Membership', 'title': 'Plans that flex with you'},
        'spaces': {'eyebrow': 'Spaces', 'title': 'Rooms for every kind of work'},
        'gallery': {'eyebrow': 'Gallery', 'title': 'Inside our spaces'},
        'members': {'eyebrow': 'Members'},
        'faq': {'eyebrow': 'FAQ', 'title': 'Questions, answered'},
        'contact': {'eyebrow': 'Book a tour', 'title': 'Come see your next workspace',
                    'body': "Tell us a little about your team and we'll set up a walkthrough at the location that fits you best."},
    }


def _default_nav_menus():
    return [
        {'label': 'Solutions', 'key': 'solutions', 'scroll': 'packages',
         'promo': {'text': "Every way you work, perfectly accommodated. Whether you're building a startup, meeting clients, or growing your team, Vivid Space offers flexible workspaces and business solutions designed to support your success.",
                   'cta': 'Explore All Solutions'},
         'columns': [
             {'heading': 'Workspace Solutions', 'links': ['Private Office', 'Dedicated Desk', 'Membership', 'Daily Cowork']},
             {'heading': 'Business Solutions', 'links': ['Virtual Office', 'Virtual Plus', 'Daily Private Office', 'Meeting Rooms']},
             {'heading': 'Included Features', 'links': ['High-Speed Internet', 'Backup Electricity & Generator', 'Receptionist Services', 'Coffee & Water', 'Office Cleaning', 'Meeting Room Access', 'IT Support', 'Legal Consultancy', 'Logo & Branding Consultancy']},
         ]},
        {'label': 'Partnerships', 'key': 'partnerships',
         'promo': {'text': 'Your perfect office, desk or meeting space. Explore every way Vivid Space can work for your team.', 'cta': 'See all solutions'},
         'columns': [
             {'heading': 'Work with us', 'links': ['Landlords', 'Enterprise', 'Brokers']},
             {'heading': 'Programs', 'links': ['Refer a Friend']},
         ]},
        {'label': 'Who we are', 'key': 'about',
         'promo': {'text': 'Our workspaces build connection, belonging, and excitement.', 'cta': 'Our approach to work'},
         'columns': [{'heading': 'Company', 'links': ['About', 'Careers', 'Blog']}]},
        {'label': 'Book A Tour', 'key': 'book-a-tour',
         'promo': {'text': 'Experience Vivid Space in Person. Discover inspiring workspaces, explore our amenities, and find the perfect environment for your business.', 'cta': 'Book Your Tour'},
         'columns': [{'heading': 'Tour Information', 'links': ['30–45 Minute Guided Tour', 'Explore Every Workspace', 'Meet Our Workspace Advisors']}]},
    ]


class SiteContent(models.Model):
    """Singleton holding editable public-website content (hero, gallery, services)."""

    hero_headline = models.CharField(max_length=200, default='Space to do your vivid best work.')
    hero_subheading = models.TextField(
        default='Light-filled desks, private offices, and meeting rooms designed for focus.'
    )
    # Hero background media: an 'image' or a 'video' at hero_media_url (blank = built-in default).
    class HeroMedia(models.TextChoices):
        IMAGE = 'image', 'Image'
        VIDEO = 'video', 'Video'

    hero_media_type = models.CharField(max_length=10, choices=HeroMedia.choices, default=HeroMedia.IMAGE)
    hero_media_url = models.CharField(max_length=500, blank=True, default='')
    # [{ "label": "Lobby" }, ...]
    gallery = models.JSONField(default=list, blank=True)
    # [{ "icon": "wifi", "name": "1 Gbps Wi-Fi" }, ...]
    services = models.JSONField(default=list, blank=True)
    # Member testimonials: [{ "quote": "...", "author": "...", "company": "...", "image": "/media/..." }, ...]
    testimonials = models.JSONField(default=list, blank=True)
    # Fully data-driven page content (editable in the admin).
    intro_text = models.TextField(default=_default_intro)
    stats = models.JSONField(default=_default_stats, blank=True)
    solutions = models.JSONField(default=_default_solutions, blank=True)
    hero_cards = models.JSONField(default=_default_hero_cards, blank=True)
    footer = models.JSONField(default=_default_footer, blank=True)
    headings = models.JSONField(default=_default_headings, blank=True)
    nav_menus = models.JSONField(default=_default_nav_menus, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Site content'
        verbose_name_plural = 'Site content'

    def __str__(self):
        return 'Site content'

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class AdminSettings(models.Model):
    """Singleton holding center-wide booking rules and details."""

    allow_sameday = models.BooleanField(default=True)
    auto_approve = models.BooleanField(default=False)
    pay_at_center = models.BooleanField(default=True)
    sameday_cutoff = models.CharField(max_length=60, default='No cutoff — allow any time')
    center_name = models.CharField(max_length=120, default='Vivid Space — Hudson St')
    opening_hours = models.CharField(max_length=120, default='Mon–Fri 7am–9pm · Members 24/7')
    # Structured business hours used by the availability endpoint. Shape:
    # {"mon": {"open": "07:00", "close": "21:00", "closed": false}, ...}.
    # The opening_hours string above remains the human-readable display label.
    business_hours = models.JSONField(default=dict, blank=True)
    # Recipient for tour-request notification emails. Falls back to OWNER_EMAIL env.
    notification_email = models.EmailField(blank=True)
    # Public contact details, surfaced via GET /api/site/.
    contact_email = models.EmailField(blank=True)
    phones = models.JSONField(default=list, blank=True)  # ["+1 555 0100", ...]
    address = models.CharField(max_length=240, blank=True)
    maps_url = models.CharField(max_length=500, blank=True)  # Google Maps link/embed
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Admin settings'
        verbose_name_plural = 'Admin settings'

    def __str__(self):
        return 'Admin settings'

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class PromoCode(models.Model):
    """A referral code handed out by a salesperson or campaign, tracked on tours."""

    code = models.CharField(max_length=40, unique=True)
    # Campaign or partner label, e.g. "Spring Launch" or "Northwind Partners".
    campaign = models.CharField(max_length=120, blank=True)
    # The sales rep this code is attributed to.
    sales_rep = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return self.code

    def save(self, *args, **kwargs):
        if self.code:
            self.code = self.code.strip().upper()
        super().save(*args, **kwargs)

    @property
    def tour_count(self):
        return self.tour_requests.count()


class TourRequest(models.Model):
    """A "Book a Tour" submission from the public website."""

    class Status(models.TextChoices):
        NEW = 'new', 'New'
        CONTACTED = 'contacted', 'Contacted'
        SCHEDULED = 'scheduled', 'Scheduled'
        CLOSED = 'closed', 'Closed'

    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    email = models.EmailField()
    phone = models.CharField(max_length=40)
    # Resolved promo code (if the submitted code matched an active one) plus the
    # raw text the visitor typed, kept regardless of whether it resolved.
    promo_code = models.ForeignKey(
        PromoCode, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tour_requests',
    )
    promo_code_text = models.CharField(max_length=40, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.NEW)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.first_name} {self.last_name} · {self.email}'

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'.strip()


class CustomizationRequest(models.Model):
    """A public 'build your own package' enquiry from the website.

    Stores the visitor's contact details plus their day-by-day mix of office
    types so a lead is never lost even if the owner-notification email fails.
    """

    class Status(models.TextChoices):
        NEW = 'new', 'New'
        CONTACTED = 'contacted', 'Contacted'
        SCHEDULED = 'scheduled', 'Scheduled'
        CLOSED = 'closed', 'Closed'

    name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=40, blank=True)
    details = models.TextField(blank=True)
    # [{ "office": "Private Office", "dates": ["2026-08-01", ...] }, ...]
    items = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.NEW)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} · {self.email}'

    @property
    def total_days(self):
        return sum(len(it.get('dates') or []) for it in (self.items or []))


class BlockedSlot(models.Model):
    """An admin-defined block making a space (or all spaces) unavailable."""

    # Null space => the block applies to every space that day/time.
    space = models.ForeignKey(
        Space, on_delete=models.CASCADE, null=True, blank=True, related_name='blocked_slots'
    )
    date = models.DateField()
    # Null start/end => the whole day is blocked.
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    reason = models.CharField(max_length=160, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date', 'start_time']

    def __str__(self):
        scope = self.space.name if self.space else 'All spaces'
        return f'{scope} · {self.date}'

    def covers(self, start, end):
        """Whether this block overlaps a requested [start, end) window.

        A full-day block (no times) covers everything on its date; otherwise it
        overlaps when the ranges intersect. A full-day *booking* (start is None)
        collides with any block on the date.
        """
        if self.start_time is None or self.end_time is None:
            return True
        if start is None or end is None:
            return True
        return start < self.end_time and self.start_time < end


class GalleryImage(models.Model):
    """An image shown in the public gallery, admin-managed and reorderable."""

    # Stores the URL returned by the /api/admin/upload/ flow (e.g. /media/gallery/x.png).
    image = models.CharField(max_length=500)
    caption = models.CharField(max_length=160, blank=True)
    # Optional grouping label, e.g. "Lounge" or "Meeting rooms".
    category = models.CharField(max_length=80, blank=True)
    order = models.PositiveIntegerField(default=0)
    is_visible = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return self.caption or self.image


class FAQ(models.Model):
    """A frequently-asked question shown on the public site, admin-managed."""

    question = models.CharField(max_length=240)
    answer = models.TextField()
    order = models.PositiveIntegerField(default=0)
    is_visible = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'id']
        verbose_name = 'FAQ'
        verbose_name_plural = 'FAQs'

    def __str__(self):
        return self.question
