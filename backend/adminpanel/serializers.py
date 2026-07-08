from django.contrib.auth import get_user_model
from rest_framework import serializers

from bookings.models import (
    AdminSettings, BlockedSlot, Booking, CustomizationRequest, MembershipPlan,
    PackageCategory, PromoCode, SiteContent, Space, TourRequest,
)
from bookings.serializers import MONTHS, validate_safe_url

User = get_user_model()

STATUS_STYLES = {
    'confirmed': ('rgba(46,115,224,.16)', '#6BA4F5', 'Confirmed'),
    'pending': ('rgba(240,130,46,.16)', '#F3A35E', 'Pending'),
    'change': ('rgba(155,126,189,.18)', '#9B7EBD', 'Change requested'),
    'completed': ('rgba(255,255,255,.07)', 'rgba(255,255,255,.6)', 'Completed'),
    'cancelled': ('rgba(226,58,75,.14)', '#F06A78', 'Cancelled'),
}


class AdminUserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    plan = serializers.SerializerMethodField()
    schedule_change_requested = serializers.SerializerMethodField()
    schedule_change_days = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id', 'uuid', 'email', 'first_name', 'last_name', 'company', 'full_name',
            'role', 'is_approved', 'is_active', 'date_joined', 'plan',
            'schedule_change_requested', 'schedule_change_days',
        )
        read_only_fields = fields

    def get_plan(self, obj):
        membership = getattr(obj, 'membership', None)
        return membership.display_name if membership else None

    def get_schedule_change_requested(self, obj):
        membership = getattr(obj, 'membership', None)
        return bool(membership and membership.has_schedule_change)

    def get_schedule_change_days(self, obj):
        membership = getattr(obj, 'membership', None)
        if not membership or not membership.has_schedule_change:
            return 0
        return sum(len(c.get('dates') or []) for c in (membership.pending_components or [])
                   if isinstance(c, dict) and not c.get('lifetime'))


class ClientSerializer(serializers.ModelSerializer):
    """Active-client row for the admin Clients table."""

    full_name = serializers.CharField(read_only=True)
    initials = serializers.SerializerMethodField()
    package = serializers.SerializerMethodField()
    perks = serializers.SerializerMethodField()
    room_hours_left = serializers.SerializerMethodField()
    room_hours_used = serializers.SerializerMethodField()
    effective_hours = serializers.SerializerMethodField()
    bookings_count = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id', 'full_name', 'email', 'company', 'initials', 'package', 'perks',
            'is_active', 'room_hours_left', 'room_hours_used', 'effective_hours',
            'bookings_count',
        )

    def get_initials(self, obj):
        name = obj.full_name
        return ''.join(p[0] for p in name.split()[:2]).upper() or 'VS'

    def get_package(self, obj):
        membership = getattr(obj, 'membership', None)
        return membership.display_name if membership else '—'

    def get_perks(self, obj):
        membership = getattr(obj, 'membership', None)
        if not membership:
            return '—'
        bits = []
        if membership.plan.guest_passes:
            bits.append(f'{membership.plan.guest_passes} guest passes')
        if membership.effective_hours:
            bits.append(f'{membership.effective_hours} room hrs')
        return ', '.join(bits) or '—'

    def get_room_hours_left(self, obj):
        membership = getattr(obj, 'membership', None)
        return membership.room_hours_left if membership else 0

    def get_room_hours_used(self, obj):
        membership = getattr(obj, 'membership', None)
        return float(membership.room_hours_used) if membership else 0

    def get_effective_hours(self, obj):
        membership = getattr(obj, 'membership', None)
        return membership.effective_hours if membership else 0

    def get_bookings_count(self, obj):
        return obj.bookings.exclude(status=Booking.Status.CANCELLED).count()


class ReservationSerializer(serializers.ModelSerializer):
    """Booking shaped for the admin reservations table."""

    client = serializers.SerializerMethodField()
    company = serializers.CharField(source='user.company', read_only=True)
    space_label = serializers.SerializerMethodField()
    duration_label = serializers.SerializerMethodField()
    date_label = serializers.SerializerMethodField()
    status = serializers.CharField(source='reservation_status', read_only=True)
    status_label = serializers.SerializerMethodField()
    status_bg = serializers.SerializerMethodField()
    status_color = serializers.SerializerMethodField()
    pending = serializers.BooleanField(source='is_pending', read_only=True)
    change_requested = serializers.BooleanField(read_only=True)
    requested_label = serializers.SerializerMethodField()
    cancellable = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = (
            'id', 'client', 'company', 'space_label', 'duration', 'duration_label',
            'date', 'date_label', 'free', 'is_free', 'is_paid', 'status',
            'status_label', 'status_bg', 'status_color', 'pending',
            'change_requested', 'requested_label', 'cancellable',
        )

    free = serializers.BooleanField(source='is_free', read_only=True)

    def get_client(self, obj):
        return obj.user.full_name

    def get_space_label(self, obj):
        return f'{obj.space.name} · {obj.unit}' if obj.unit else obj.space.name

    def get_duration_label(self, obj):
        if obj.duration == Booking.Duration.HOURLY and obj.start_time:
            s = obj.start_time.strftime('%H:%M')
            return f'Hourly · {s}' + (f'–{obj.end_time.strftime("%H:%M")}' if obj.end_time else '')
        return 'Full day'

    def get_date_label(self, obj):
        return f'{MONTHS[obj.date.month - 1]} {obj.date.day:02d}'

    def get_status_label(self, obj):
        return STATUS_STYLES[obj.reservation_status][2]

    def get_status_bg(self, obj):
        return STATUS_STYLES[obj.reservation_status][0]

    def get_status_color(self, obj):
        return STATUS_STYLES[obj.reservation_status][1]

    def get_requested_label(self, obj):
        """The member's proposed new date/time, e.g. 'Aug 11 · 14:00'."""
        if not obj.change_requested or not obj.requested_date:
            return ''
        d = obj.requested_date
        label = f'{MONTHS[d.month - 1]} {d.day:02d}'
        if obj.duration == Booking.Duration.HOURLY and obj.requested_start_time:
            label += f' · {obj.requested_start_time.strftime("%H:%M")}'
        else:
            label += ' · Full day'
        return label

    def get_cancellable(self, obj):
        return not obj.is_cancelled and not obj.is_past


class ReservationEditSerializer(serializers.ModelSerializer):
    """Editable fields from the admin edit-reservation modal."""

    class Meta:
        model = Booking
        fields = ('unit', 'date', 'duration', 'start_time', 'end_time', 'status', 'is_paid')
        extra_kwargs = {f: {'required': False} for f in fields}


class AdminSpaceSerializer(serializers.ModelSerializer):
    meta = serializers.CharField(read_only=True)
    availability_status = serializers.SerializerMethodField()

    class Meta:
        model = Space
        fields = (
            'id', 'key', 'name', 'icon', 'icon_color', 'gradient', 'description',
            'capacity', 'size', 'amenities', 'equipment', 'images', 'video_url',
            'is_free', 'uses_free_hours', 'durations', 'day_price', 'hour_price', 'units', 'rates',
            'is_active', 'booking_enabled', 'admin_status', 'availability_status',
            'order', 'meta',
        )

    def get_availability_status(self, obj):
        return obj.availability_status()


class AdminPackageCategorySerializer(serializers.ModelSerializer):
    plan_count = serializers.SerializerMethodField()

    class Meta:
        model = PackageCategory
        fields = ('id', 'name', 'slug', 'description', 'order', 'is_visible',
                  'plan_count', 'created_at')
        read_only_fields = ('slug', 'created_at')

    def get_plan_count(self, obj):
        return obj.plans.count()


class PackageSerializer(serializers.ModelSerializer):
    members = serializers.IntegerField(source='member_count', read_only=True)
    display_price = serializers.CharField(read_only=True)
    category = serializers.PrimaryKeyRelatedField(
        queryset=PackageCategory.objects.all(), allow_null=True, required=False,
    )
    category_name = serializers.CharField(source='category.name', read_only=True, default=None)
    category_slug = serializers.CharField(source='category.slug', read_only=True, default=None)

    class Meta:
        model = MembershipPlan
        fields = (
            'id', 'name', 'category', 'category_name', 'category_slug', 'description',
            'price', 'price_label', 'display_price', 'period', 'featured', 'badge',
            'room_hours', 'guest_passes', 'features', 'images', 'video_url', 'details',
            'perk_note', 'is_active', 'booking_enabled', 'is_visible', 'is_archived',
            'order', 'members',
        )


class SiteContentSerializer(serializers.ModelSerializer):
    class Meta:
        model = SiteContent
        fields = ('hero_headline', 'hero_subheading', 'hero_media_type', 'hero_media_url',
                  'gallery', 'services', 'testimonials', 'intro_text', 'stats', 'solutions',
                  'hero_cards', 'footer', 'headings', 'nav_menus', 'updated_at')
        read_only_fields = ('updated_at',)

    def validate_hero_media_url(self, value):
        # Rendered as media src on the public homepage — reject javascript:/data:
        # and other script-capable schemes.
        return validate_safe_url(value)


class AdminSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdminSettings
        fields = (
            'allow_sameday', 'auto_approve', 'pay_at_center', 'sameday_cutoff',
            'center_name', 'opening_hours', 'business_hours', 'notification_email',
            'contact_email', 'phones', 'address', 'maps_url',
            'whatsapp_number', 'whatsapp_message', 'updated_at',
        )
        read_only_fields = ('updated_at',)

    def validate_maps_url(self, value):
        # Rendered in an <a href> / <iframe src> on the public homepage — must
        # be a real web URL, never javascript:/data:.
        return validate_safe_url(value)


class PromoCodeSerializer(serializers.ModelSerializer):
    tour_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = PromoCode
        fields = ('id', 'code', 'campaign', 'sales_rep', 'is_active', 'tour_count', 'created_at')
        read_only_fields = ('tour_count', 'created_at')


class TourRequestSerializer(serializers.ModelSerializer):
    """Book-a-Tour submission shaped for the admin Tour Requests table."""

    full_name = serializers.CharField(read_only=True)
    promo_code = serializers.CharField(source='promo_code.code', read_only=True, default=None)
    status_label = serializers.CharField(source='get_status_display', read_only=True)
    date_label = serializers.SerializerMethodField()

    class Meta:
        model = TourRequest
        fields = (
            'id', 'first_name', 'last_name', 'full_name', 'email', 'phone',
            'promo_code', 'promo_code_text', 'status', 'status_label',
            'created_at', 'date_label',
        )
        read_only_fields = (
            'first_name', 'last_name', 'email', 'phone', 'promo_code',
            'promo_code_text', 'created_at',
        )

    def get_date_label(self, obj):
        return f'{MONTHS[obj.created_at.month - 1]} {obj.created_at.day:02d}'


class CustomizationRequestSerializer(serializers.ModelSerializer):
    """A public 'build your own package' enquiry, for the admin table."""

    total_days = serializers.IntegerField(read_only=True)
    status_label = serializers.CharField(source='get_status_display', read_only=True)
    date_label = serializers.SerializerMethodField()

    class Meta:
        model = CustomizationRequest
        fields = (
            'id', 'name', 'email', 'phone', 'details', 'items', 'total_days',
            'status', 'status_label', 'created_at', 'date_label',
        )
        read_only_fields = (
            'name', 'email', 'phone', 'details', 'items', 'created_at',
        )

    def get_date_label(self, obj):
        return f'{MONTHS[obj.created_at.month - 1]} {obj.created_at.day:02d}'


class BlockedSlotSerializer(serializers.ModelSerializer):
    space_key = serializers.SlugRelatedField(
        source='space', slug_field='key', queryset=Space.objects.all(),
        required=False, allow_null=True,
    )
    space_name = serializers.CharField(source='space.name', read_only=True, default='All spaces')

    class Meta:
        model = BlockedSlot
        fields = (
            'id', 'space_key', 'space_name', 'date', 'start_time', 'end_time',
            'reason', 'created_at',
        )
        read_only_fields = ('created_at',)
