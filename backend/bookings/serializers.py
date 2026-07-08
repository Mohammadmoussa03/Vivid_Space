from datetime import datetime, timedelta

from django.db import transaction
from django.db.models import Q
from rest_framework import serializers

from .models import (
    BlockedSlot, Booking, FAQ, GalleryImage, Membership, MembershipPlan,
    PackageCategory, PromoCode, Space, TourRequest,
)

MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
          'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']


def validate_safe_url(value):
    """Allow only http(s) absolute URLs or site-relative paths (e.g. /media/…).

    Blocks script-capable schemes (javascript:, data:, vbscript:) that would turn
    an admin-controlled URL rendered in an href/iframe into stored XSS.
    """
    if value in (None, ''):
        return value
    v = str(value).strip()
    low = v.lower()
    if low.startswith(('http://', 'https://')) or v.startswith('/'):
        return v
    raise serializers.ValidationError(
        'Enter a valid http(s) URL (or a site-relative /path).'
    )


def _money(value):
    """Render a Decimal as a clean dollar string ($90, $12.50)."""
    if value is None:
        return ''
    if value == value.to_integral_value():
        return f'${int(value)}'
    return f'${value.normalize()}'


class CategoryMiniSerializer(serializers.ModelSerializer):
    """Compact category reference nested inside packages."""

    class Meta:
        model = PackageCategory
        fields = ('id', 'slug', 'name')


class PackageCategorySerializer(serializers.ModelSerializer):
    plan_count = serializers.SerializerMethodField()

    class Meta:
        model = PackageCategory
        fields = ('id', 'name', 'slug', 'description', 'order', 'is_visible',
                  'plan_count', 'created_at')
        read_only_fields = ('slug', 'created_at')

    def get_plan_count(self, obj):
        return obj.plans.count()


class SpaceSerializer(serializers.ModelSerializer):
    """Full workspace detail — superset used by both the public site and portal."""

    meta = serializers.CharField(read_only=True)
    free = serializers.BooleanField(source='is_free', read_only=True)
    availability_status = serializers.SerializerMethodField()

    class Meta:
        model = Space
        fields = (
            'id', 'key', 'name', 'icon', 'icon_color', 'gradient', 'meta', 'free',
            'description', 'capacity', 'size', 'amenities', 'equipment', 'images',
            'video_url', 'durations', 'day_price', 'hour_price', 'units', 'rates', 'is_free',
            'uses_free_hours', 'is_active', 'booking_enabled', 'admin_status',
            'availability_status', 'order',
        )

    def get_availability_status(self, obj):
        return obj.availability_status(self.context.get('availability_date'))


class GalleryImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = GalleryImage
        fields = ('id', 'image', 'caption', 'category', 'order', 'is_visible', 'created_at')
        read_only_fields = ('created_at',)


class FAQSerializer(serializers.ModelSerializer):
    class Meta:
        model = FAQ
        fields = ('id', 'question', 'answer', 'order', 'is_visible', 'created_at')
        read_only_fields = ('created_at',)


class BookingSerializer(serializers.ModelSerializer):
    """Read shape matching the cards rendered in Portal.jsx."""

    mon = serializers.SerializerMethodField()
    day = serializers.SerializerMethodField()
    space = serializers.SerializerMethodField()
    space_key = serializers.CharField(source='space.key', read_only=True)
    time = serializers.SerializerMethodField()
    cost = serializers.SerializerMethodField()
    free = serializers.BooleanField(source='is_free', read_only=True)
    status = serializers.CharField(source='status_label', read_only=True)
    when = serializers.CharField(read_only=True)
    change_requested = serializers.BooleanField(read_only=True)
    requested = serializers.SerializerMethodField()

    class Meta:
        model = Booking
        fields = (
            'id', 'mon', 'day', 'space', 'space_key', 'unit', 'date',
            'duration', 'start_time', 'end_time', 'time', 'cost',
            'attendees', 'free', 'status', 'when',
            'change_requested', 'requested',
        )

    def get_mon(self, obj):
        return MONTHS[obj.date.month - 1]

    def get_day(self, obj):
        return f'{obj.date.day:02d}'

    def get_space(self, obj):
        return f'{obj.space.name} · {obj.unit}' if obj.unit else obj.space.name

    def get_time(self, obj):
        if obj.duration == Booking.Duration.HOURLY and obj.start_time:
            start = obj.start_time.strftime('%H:%M')
            if obj.end_time:
                return f'{start} – {obj.end_time.strftime("%H:%M")}'
            return start
        return 'Full day'

    def get_cost(self, obj):
        if obj.is_free:
            return 'Free'
        if obj.when == 'past':
            return f'Paid {_money(obj.price)}'.strip() if obj.price else 'Paid'
        return 'Pay at center'

    def get_requested(self, obj):
        """The pending reschedule the member submitted, awaiting admin review."""
        if not obj.change_requested or not obj.requested_date:
            return None
        d = obj.requested_date
        if obj.duration == Booking.Duration.HOURLY and obj.requested_start_time:
            time = obj.requested_start_time.strftime('%H:%M')
        else:
            time = 'Full day'
        return {
            'date': d.isoformat(),
            'mon': MONTHS[d.month - 1],
            'day': f'{d.day:02d}',
            'time': time,
        }


def _slot_end(booking_date, start, hours):
    return (datetime.combine(booking_date, start) + timedelta(hours=hours)).time()


class BookingCreateSerializer(serializers.ModelSerializer):
    space = serializers.SlugRelatedField(slug_field='key', queryset=Space.objects.filter(is_active=True))
    # Length of an hourly booking; defaults to 1. Ignored for full-day bookings.
    hours = serializers.IntegerField(write_only=True, required=False, min_value=1, max_value=12)

    class Meta:
        model = Booking
        fields = ('id', 'space', 'unit', 'date', 'duration', 'start_time', 'hours', 'attendees')

    # ---- availability helpers ----

    @staticmethod
    def _overlap_conflict(space, booking_date, unit, start, end, exclude_pk=None):
        """Return an error message if the requested slot collides with existing
        bookings, respecting per-unit uniqueness and overall space capacity."""
        qs = (Booking.objects.filter(space=space, date=booking_date)
              .exclude(status=Booking.Status.CANCELLED))
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)

        def overlaps(b):
            # A full-day booking (new or existing) occupies the unit all day.
            if start is None or end is None:
                return True
            if b.duration == Booking.Duration.FULLDAY or not b.start_time or not b.end_time:
                return True
            return start < b.end_time and b.start_time < end

        conflicting = [b for b in qs if overlaps(b)]
        if unit:
            if any((b.unit or '').lower() == unit.lower() for b in conflicting):
                return 'That unit is already booked for the selected time.'
            return None
        if len(conflicting) >= (space.units or 1):
            return 'That time slot is fully booked.'
        return None

    @staticmethod
    def _blocked(space, booking_date, start, end):
        blocks = (BlockedSlot.objects.filter(date=booking_date)
                  .filter(Q(space=space) | Q(space__isnull=True)))
        for b in blocks:
            if b.covers(start, end):
                return b.reason or 'That time has been blocked off.'
        return None

    def validate(self, attrs):
        space = attrs['space']
        duration = attrs.get('duration', Booking.Duration.HOURLY)
        hours = attrs.get('hours') or 1

        if space.durations and duration not in space.durations:
            raise serializers.ValidationError(
                {'duration': f'{space.name} does not support "{duration}" bookings.'}
            )

        attendees = attrs.get('attendees')
        if attendees and space.capacity and attendees > space.capacity:
            raise serializers.ValidationError(
                {'attendees': f'{space.name} holds up to {space.capacity} people.'}
            )

        if duration == Booking.Duration.HOURLY:
            start = attrs.get('start_time')
            if not start:
                raise serializers.ValidationError({'start_time': 'Pick a start time for hourly bookings.'})
            end = _slot_end(attrs['date'], start, hours)
        else:
            start = end = None

        conflict = self._overlap_conflict(space, attrs['date'], attrs.get('unit', ''), start, end)
        if conflict:
            raise serializers.ValidationError({'detail': conflict})

        blocked = self._blocked(space, attrs['date'], start, end)
        if blocked:
            raise serializers.ValidationError({'detail': blocked})

        # Free meeting-room hours: verify the member has enough balance.
        if space.uses_free_hours and duration == Booking.Duration.HOURLY:
            membership = Membership.objects.filter(
                user=self.context['request'].user
            ).select_related('plan').first()
            if membership:
                membership.sync_period()
                if membership.room_hours_left < hours:
                    raise serializers.ValidationError(
                        {'detail': f'Not enough free meeting-room hours '
                                   f'({membership.room_hours_left:g} left, {hours} needed).'}
                    )
        return attrs

    def create(self, validated_data):
        space = validated_data['space']
        duration = validated_data.get('duration', Booking.Duration.HOURLY)
        start = validated_data.get('start_time')
        hours = validated_data.pop('hours', None) or 1
        user = self.context['request'].user

        if duration == Booking.Duration.HOURLY and start:
            validated_data['end_time'] = _slot_end(validated_data['date'], start, hours)
        else:
            validated_data['start_time'] = None

        validated_data['is_free'] = space.is_free
        if space.is_free:
            validated_data['price'] = None
        elif duration == Booking.Duration.HOURLY:
            # Charge the hourly rate × hours; fall back to the day rate if unset.
            rate = space.hour_price if space.hour_price is not None else space.day_price
            validated_data['price'] = (rate or 0) * hours
        else:
            validated_data['price'] = space.day_price
        validated_data['user'] = user

        with transaction.atomic():
            deducted = 0
            if space.uses_free_hours and duration == Booking.Duration.HOURLY:
                membership = (Membership.objects.select_for_update()
                              .filter(user=user).select_related('plan').first())
                if membership:
                    membership.sync_period()
                    if membership.room_hours_left < hours:
                        raise serializers.ValidationError(
                            {'detail': 'Not enough free meeting-room hours.'}
                        )
                    membership.room_hours_used = float(membership.room_hours_used) + hours
                    membership.save(update_fields=['room_hours_used', 'hours_period'])
                    deducted = hours
                    validated_data['is_free'] = True
                    validated_data['price'] = None
            validated_data['free_hours_used'] = deducted
            return super().create(validated_data)

    def to_representation(self, instance):
        return BookingSerializer(instance, context=self.context).data


class TourRequestCreateSerializer(serializers.ModelSerializer):
    """Public Book-a-Tour submission."""

    promo_code = serializers.CharField(
        source='promo_code_text', required=False, allow_blank=True, max_length=40,
    )

    class Meta:
        model = TourRequest
        fields = ('id', 'first_name', 'last_name', 'email', 'phone', 'promo_code')

    def create(self, validated_data):
        code_text = (validated_data.get('promo_code_text') or '').strip()
        validated_data['promo_code_text'] = code_text
        if code_text:
            validated_data['promo_code'] = PromoCode.objects.filter(
                code__iexact=code_text, is_active=True
            ).first()
        return super().create(validated_data)


class CustomizationItemSerializer(serializers.Serializer):
    """One office in a bespoke package, with the days the visitor wants it and,
    optionally, the time of day: a full day (default) or a specific start time
    with a number of hours."""

    office = serializers.CharField(max_length=120)
    dates = serializers.ListField(
        child=serializers.DateField(), allow_empty=False, max_length=366,
    )
    duration = serializers.ChoiceField(
        choices=('fullday', 'hourly'), required=False, default='fullday',
    )
    start_time = serializers.TimeField(required=False, allow_null=True)
    hours = serializers.IntegerField(required=False, min_value=1, max_value=12, allow_null=True)

    def validate(self, attrs):
        if attrs.get('duration') == 'hourly' and not attrs.get('start_time'):
            raise serializers.ValidationError(
                {'start_time': 'Pick a start time for an hourly office.'}
            )
        return attrs


class CustomizationRequestSerializer(serializers.Serializer):
    """Public 'customize my package' enquiry. Not persisted — emailed to the owner."""

    name = serializers.CharField(max_length=120)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=40, required=False, allow_blank=True)
    # A bespoke package mixes any number of offices, each with its own set of days.
    items = CustomizationItemSerializer(many=True, allow_empty=False, max_length=20)
    details = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class PackagePublicSerializer(serializers.ModelSerializer):
    """Public read shape for the Packages page, one row per plan."""

    display_price = serializers.CharField(read_only=True)
    category = CategoryMiniSerializer(read_only=True)

    class Meta:
        model = MembershipPlan
        fields = (
            'id', 'name', 'category', 'description', 'price', 'display_price', 'period',
            'featured', 'badge', 'room_hours', 'guest_passes', 'features', 'images',
            'video_url', 'details', 'perk_note', 'booking_enabled',
        )


class MembershipPlanSerializer(serializers.ModelSerializer):
    category = CategoryMiniSerializer(read_only=True)

    class Meta:
        model = MembershipPlan
        fields = ('id', 'name', 'category', 'price', 'room_hours', 'guest_passes',
                  'features', 'perk_note')


class MembershipSerializer(serializers.ModelSerializer):
    plan = MembershipPlanSerializer(read_only=True)
    room_hours_left = serializers.FloatField(read_only=True)
    guest_passes_left = serializers.IntegerField(read_only=True)
    effective_hours = serializers.IntegerField(read_only=True)
    price_display = serializers.CharField(read_only=True)
    is_custom = serializers.BooleanField(read_only=True)
    display_name = serializers.CharField(read_only=True)
    schedule_change_requested = serializers.BooleanField(read_only=True)
    pending_components = serializers.JSONField(read_only=True)

    class Meta:
        model = Membership
        fields = (
            'status', 'member_since', 'room_hours_used', 'room_hours_left',
            'effective_hours', 'guest_passes_used', 'guest_passes_left',
            'custom_components', 'custom_price', 'custom_price_label',
            'custom_plan_name', 'display_name', 'price_display', 'is_custom', 'plan',
            'schedule_change_requested', 'pending_components',
        )
