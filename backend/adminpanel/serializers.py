from django.contrib.auth import get_user_model
from rest_framework import serializers

from bookings.models import (
    AdminSettings, BlockedSlot, Booking, CustomizationRequest, MembershipPlan,
    Order, PackageCategory, PromoCode, SiteContent, Space, TourRequest,
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
    email = serializers.EmailField(source='user.email', read_only=True)
    space_label = serializers.SerializerMethodField()
    space_name = serializers.CharField(source='space.name', read_only=True)
    duration_label = serializers.SerializerMethodField()
    date_label = serializers.SerializerMethodField()
    time_label = serializers.SerializerMethodField()
    status = serializers.CharField(source='reservation_status', read_only=True)
    status_label = serializers.SerializerMethodField()
    status_bg = serializers.SerializerMethodField()
    status_color = serializers.SerializerMethodField()
    pending = serializers.BooleanField(source='is_pending', read_only=True)
    change_requested = serializers.BooleanField(read_only=True)
    requested_label = serializers.SerializerMethodField()
    cancellable = serializers.SerializerMethodField()
    price_display = serializers.SerializerMethodField()
    order_number = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = (
            'id', 'client', 'company', 'email', 'space_label', 'space_name', 'unit',
            'duration', 'duration_label', 'date', 'date_label', 'time_label',
            'start_time', 'end_time', 'attendees', 'free', 'is_free', 'is_paid',
            'price', 'price_display', 'free_hours_used', 'created_at', 'order_number',
            'status', 'status_label', 'status_bg', 'status_color', 'pending',
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
        # The reschedule may also switch the booking's shape; show what was asked for.
        req_duration = obj.requested_duration or obj.duration
        label = f'{MONTHS[d.month - 1]} {d.day:02d}'
        if req_duration == Booking.Duration.HOURLY and obj.requested_start_time:
            label += f' · {obj.requested_start_time.strftime("%H:%M")}'
            if obj.requested_hours:
                label += f' · {obj.requested_hours} hr{"s" if obj.requested_hours > 1 else ""}'
        else:
            label += ' · Full day'
        return label

    def get_cancellable(self, obj):
        return not obj.is_cancelled and not obj.is_past

    def get_time_label(self, obj):
        """Just the clock window, e.g. '09:00–11:00' — 'Full day' when not hourly."""
        if obj.duration != Booking.Duration.HOURLY or not obj.start_time:
            return 'Full day'
        label = obj.start_time.strftime('%H:%M')
        if obj.end_time:
            label += f'–{obj.end_time.strftime("%H:%M")}'
        return label

    def get_price_display(self, obj):
        if obj.is_free:
            return 'Free with plan'
        return f'${obj.price:.2f}' if obj.price is not None else '—'

    def get_order_number(self, obj):
        return obj.order.order_number if obj.order else ''


class ReservationEditSerializer(serializers.ModelSerializer):
    """Editable fields from the admin edit-reservation modal."""

    class Meta:
        model = Booking
        fields = ('unit', 'date', 'duration', 'start_time', 'end_time', 'status', 'is_paid')
        extra_kwargs = {f: {'required': False} for f in fields}

    def update(self, instance, validated_data):
        """When an admin changes the schedule (date/duration/times), re-settle the
        booking's free meeting-room hours and price — a raw field save would leave
        the member's balance and the price stale."""
        from datetime import datetime, date as _date, timedelta
        from bookings.views import (
            apply_booking_change, _booking_length_hours, NotEnoughHoursError,
        )

        # Non-scheduling fields save directly.
        for f in ('unit', 'status', 'is_paid'):
            if f in validated_data:
                setattr(instance, f, validated_data[f])

        sched = ('date', 'duration', 'start_time', 'end_time')
        if not any(f in validated_data for f in sched):
            instance.save()
            return instance

        new_date = validated_data.get('date', instance.date)
        duration = validated_data.get('duration', instance.duration)
        if duration == Booking.Duration.HOURLY:
            start = validated_data.get('start_time', instance.start_time)
            end = validated_data.get('end_time', instance.end_time)
            if start and end:
                delta = datetime.combine(_date.min, end) - datetime.combine(_date.min, start)
                hours = max(1, round(delta.total_seconds() / 3600))
            else:
                hours = _booking_length_hours(instance)
                start = start or instance.start_time
                end = (datetime.combine(new_date, start) + timedelta(hours=hours)).time()
        else:
            start = end = None
            hours = None

        try:
            apply_booking_change(instance, new_date, duration, start, end, hours)
        except NotEnoughHoursError as exc:
            raise serializers.ValidationError({'detail': str(exc)})
        return instance


class AdminSpaceSerializer(serializers.ModelSerializer):
    meta = serializers.CharField(read_only=True)
    availability_status = serializers.SerializerMethodField()

    def update(self, instance, validated_data):
        """Growing a space's unit count retroactively makes its existing
        unit-less bookings ambiguous (they name no room, so a new booking can be
        placed on the same physical one). Stamp them with a concrete unit as soon
        as the space stops being single-unit."""
        was_single = (instance.units or 1) <= 1
        space = super().update(instance, validated_data)
        if was_single and (space.units or 1) > 1:
            space.assign_missing_units()
        return space

    class Meta:
        model = Space
        fields = (
            'id', 'key', 'name', 'icon', 'icon_color', 'gradient', 'description',
            'capacity', 'size', 'amenities', 'equipment', 'images', 'video_url',
            'is_free', 'uses_free_hours', 'durations', 'day_price', 'hour_price', 'units',
            'unit_names', 'rates',
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
                  'hero_cards', 'footer', 'headings', 'nav_menus',
                  'about_eyebrow', 'about_title', 'about_body', 'about_points',
                  'updated_at')
        read_only_fields = ('updated_at',)

    def validate_hero_media_url(self, value):
        # Rendered as media src on the public homepage — reject javascript:/data:
        # and other script-capable schemes.
        return validate_safe_url(value)


class AdminOrderSerializer(serializers.ModelSerializer):
    """Whish payment order for the admin Payments table."""

    customer = serializers.SerializerMethodField()
    email = serializers.EmailField(source='user.email', read_only=True)
    company = serializers.CharField(source='user.company', read_only=True)
    amount_display = serializers.SerializerMethodField()
    status_label = serializers.SerializerMethodField()
    method_label = serializers.CharField(source='get_payment_method_display', read_only=True)
    bookings = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = (
            'id', 'order_number', 'customer', 'email', 'company', 'amount', 'amount_display',
            'payment_method', 'method_label', 'status', 'status_label', 'receipt_url', 'note',
            'created_at', 'paid_at', 'bookings',
        )

    def get_customer(self, obj):
        return obj.user.full_name or obj.user.email

    def get_amount_display(self, obj):
        return f'${obj.amount:.2f}'

    def get_status_label(self, obj):
        return obj.get_status_display()

    def get_bookings(self, obj):
        rows = []
        for b in obj.bookings.all():
            if b.duration == Booking.Duration.HOURLY and b.start_time:
                t = b.start_time.strftime('%H:%M')
                if b.end_time:
                    t += f'–{b.end_time.strftime("%H:%M")}'
            else:
                t = 'Full day'
            label = b.space.name + (f' · {b.unit}' if b.unit else '')
            rows.append({
                'id': b.id,
                'label': label,
                'date': b.date.isoformat(),
                'time': t,
                'space': b.space.name,
                'unit': b.unit,
                'attendees': b.attendees,
                'price': f'${b.price:.2f}' if b.price is not None else ('Free with plan' if b.is_free else '—'),
                'status_label': b.status_label,
            })
        return rows


class AdminSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = AdminSettings
        fields = (
            'allow_sameday', 'auto_approve', 'pay_at_center', 'sameday_cutoff',
            'center_name', 'opening_hours', 'business_hours', 'notification_email',
            'contact_email', 'phones', 'address', 'maps_url',
            'whatsapp_number', 'whatsapp_message',
            'whish_enabled', 'whish_number', 'whish_qr_url', 'whish_account_name',
            'updated_at',
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
