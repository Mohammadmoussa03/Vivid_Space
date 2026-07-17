import os
import uuid
from datetime import date, datetime, time, timedelta

from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    AdminSettings, BlockedSlot, Booking, CustomizationRequest, FAQ, GalleryImage,
    Membership, MembershipPlan, Order, PackageCategory, SiteContent, Space,
    business_window,
)
from .serializers import (
    BookingCreateSerializer,
    BookingSerializer,
    CustomizationRequestSerializer,
    FAQSerializer,
    GalleryImageSerializer,
    MembershipSerializer,
    OrderSerializer,
    PackageCategorySerializer,
    PackagePublicSerializer,
    SpaceSerializer,
    TourRequestCreateSerializer,
)

WEEKDAY_KEYS = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']


class SpaceViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """GET /api/spaces/ — public workspace list/detail with search & filtering."""

    serializer_class = SpaceSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = 'key'

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        raw = self.request.query_params.get('available_on')
        ctx['availability_date'] = _parse_date(raw)
        return ctx

    def get_queryset(self):
        qs = Space.objects.filter(is_active=True)
        p = self.request.query_params
        if p.get('type'):
            qs = qs.filter(key=p['type'])
        if p.get('duration'):
            qs = qs.filter(durations__contains=p['duration'])
        if p.get('min_capacity'):
            try:
                qs = qs.filter(capacity__gte=int(p['min_capacity']))
            except ValueError:
                pass
        if p.get('max_price'):
            try:
                qs = qs.filter(day_price__lte=float(p['max_price']))
            except ValueError:
                pass
        # amenity filter(s): every requested amenity must be present (JSON contains).
        for amenity in p.getlist('amenity'):
            if amenity:
                qs = qs.filter(amenities__contains=amenity)
        # availability filter is computed per-space, applied in list().
        return qs

    def list(self, request, *args, **kwargs):
        qs = self.filter_queryset(self.get_queryset())
        day = _parse_date(request.query_params.get('available_on'))
        want = request.query_params.get('status')  # optional exact-status filter
        spaces = list(qs)
        if want:
            spaces = [s for s in spaces if s.availability_status(day) == want]
        elif day:
            spaces = [s for s in spaces if s.availability_status(day) == 'available']
        resp = Response(self.get_serializer(spaces, many=True).data)
        resp['Cache-Control'] = 'no-store'  # availability_status is live — don't cache
        return resp


class PackageViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """GET /api/packages/ — public list of visible packages, filterable by category."""

    serializer_class = PackagePublicSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = MembershipPlan.objects.filter(
            is_active=True, is_visible=True, is_archived=False
        ).select_related('category')
        category = self.request.query_params.get('category')
        if category:
            qs = qs.filter(category__slug=category)
        return qs


class CategoryListView(mixins.ListModelMixin, viewsets.GenericViewSet):
    """GET /api/categories/ — public list of visible package categories."""

    serializer_class = PackageCategorySerializer
    permission_classes = [permissions.AllowAny]
    queryset = PackageCategory.objects.filter(is_visible=True)


class GalleryListView(mixins.ListModelMixin, viewsets.GenericViewSet):
    """GET /api/gallery/ — public gallery images, optionally by category."""

    serializer_class = GalleryImageSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = GalleryImage.objects.filter(is_visible=True)
        category = self.request.query_params.get('category')
        if category:
            qs = qs.filter(category=category)
        return qs


class FAQListView(mixins.ListModelMixin, viewsets.GenericViewSet):
    """GET /api/faqs/ — public FAQ list."""

    serializer_class = FAQSerializer
    permission_classes = [permissions.AllowAny]
    queryset = FAQ.objects.filter(is_visible=True)


class SiteConfigView(APIView):
    """GET /api/site/ — public site config (hero, services, contact, hours)."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        content = SiteContent.load()
        s = AdminSettings.load()
        return Response({
            'center_name': s.center_name,
            'hero': {
                'headline': content.hero_headline,
                'subheading': content.hero_subheading,
                'media_type': content.hero_media_type,
                'media_url': content.hero_media_url,
            },
            'services': content.services,
            'testimonials': content.testimonials,
            'intro_text': content.intro_text,
            'stats': content.stats,
            'solutions': content.solutions,
            'hero_cards': content.hero_cards,
            'footer': content.footer,
            'headings': content.headings,
            'nav_menus': content.nav_menus,
            'about': {
                'eyebrow': content.about_eyebrow,
                'title': content.about_title,
                'body': content.about_body,
                'points': content.about_points,
            },
            'contact': {
                'email': s.contact_email,
                'phones': s.phones,
                'address': s.address,
                'maps_url': s.maps_url,
                'whatsapp': s.whatsapp_number,
                'whatsapp_message': s.whatsapp_message,
            },
            'business_hours': s.business_hours,
            'opening_hours': s.opening_hours,
            'payments': {
                # Whish is offered only when enabled AND a receiving number is set.
                'whish_enabled': bool(s.whish_enabled and s.whish_number),
            },
        })


class TourRequestCreateView(mixins.CreateModelMixin, viewsets.GenericViewSet):
    """POST /api/tours/ — public Book-a-Tour submission (emails the owner)."""

    serializer_class = TourRequestCreateSerializer
    permission_classes = [permissions.AllowAny]
    throttle_scope = 'tour'

    def perform_create(self, serializer):
        tour = serializer.save()
        _notify_owner_of_tour(tour)


class CustomizationRequestView(APIView):
    """POST /api/customize/ — public 'build your own package' enquiry.

    Persists the enquiry (so leads survive email failures) and notifies the owner.
    """

    permission_classes = [permissions.AllowAny]
    throttle_scope = 'customize'

    def post(self, request):
        serializer = CustomizationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        # Normalise the day mix to plain ISO strings (and the optional per-office
        # time of day) for storage.
        items = []
        for it in data.get('items', []):
            entry = {
                'office': it['office'],
                'dates': [d.isoformat() if hasattr(d, 'isoformat') else str(d)
                          for d in (it.get('dates') or [])],
                'duration': it.get('duration') or 'fullday',
            }
            if entry['duration'] == 'hourly':
                st = it.get('start_time')
                entry['start_time'] = st.strftime('%H:%M') if hasattr(st, 'strftime') else (st or None)
                entry['hours'] = it.get('hours') or 1
            items.append(entry)
        CustomizationRequest.objects.create(
            name=data['name'], email=data['email'],
            phone=data.get('phone', ''), details=data.get('details', ''),
            items=items,
        )
        _notify_owner_of_customization(data)
        return Response({'ok': True}, status=status.HTTP_201_CREATED)


class AvailabilityView(APIView):
    """GET /api/availability/?space=<key>&date=YYYY-MM-DD — open/taken/blocked slots."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        key = request.query_params.get('space')
        date_str = request.query_params.get('date')
        if not key or not date_str:
            return Response({'detail': 'space and date are required.'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            day = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response({'detail': 'date must be YYYY-MM-DD.'},
                            status=status.HTTP_400_BAD_REQUEST)
        space = Space.objects.filter(key=key, is_active=True).first()
        if not space:
            return Response({'detail': 'Unknown space.'}, status=status.HTTP_404_NOT_FOUND)

        settings_obj = AdminSettings.load()
        hours_cfg = (settings_obj.business_hours or {}).get(WEEKDAY_KEYS[day.weekday()], {})
        closed = bool(hours_cfg.get('closed'))
        open_str = hours_cfg.get('open', '09:00')
        close_str = hours_cfg.get('close', '18:00')
        open_h = _parse_hour(open_str, 9)
        close_h = _parse_hour(close_str, 18)

        bookings = list(space.bookings.filter(date=day).exclude(status=Booking.Status.CANCELLED))
        blocks = list(BlockedSlot.objects.filter(date=day)
                      .filter(Q(space=space) | Q(space__isnull=True)))

        # "Now" for past-slot filtering: only relevant when the date is today.
        now = timezone.localtime()
        is_today = day == now.date()
        is_past_day = day < now.date()

        taken = [{'start': b.start_time.strftime('%H:%M') if b.start_time else None,
                  'end': b.end_time.strftime('%H:%M') if b.end_time else None,
                  'fullday': b.duration == Booking.Duration.FULLDAY,
                  'unit': b.unit or ''}
                 for b in bookings]

        blocked = [{'start': b.start_time.strftime('%H:%M') if b.start_time else None,
                    'end': b.end_time.strftime('%H:%M') if b.end_time else None,
                    'reason': b.reason} for b in blocks]

        capacity = space.units or 1
        slots = []
        if not closed and not is_past_day:
            for h in range(open_h, close_h):
                slot_start = time(h, 0)
                slot_end = time(h + 1, 0) if h + 1 < 24 else time(23, 59)
                overlapping = sum(
                    1 for b in bookings
                    if b.duration == Booking.Duration.FULLDAY or not b.start_time or not b.end_time
                    or (slot_start < b.end_time and b.start_time < slot_end)
                )
                is_blocked = any(bl.covers(slot_start, slot_end) for bl in blocks)
                is_past = is_today and slot_start <= now.time()
                slots.append({
                    'time': slot_start.strftime('%H:%M'),
                    'available': (not is_blocked) and (not is_past) and overlapping < capacity,
                    'past': is_past,
                })

        fullday_taken = any(b.duration == Booking.Duration.FULLDAY for b in bookings)
        fullday_blocked = any(bl.covers(None, None) for bl in blocks)
        # Distinct physical units occupied at any point that day (a new full-day
        # booking needs a unit free all day). Count named units once + each unnamed
        # booking — not raw rows, so two hourly bookings of the *same* unit don't
        # look like two occupied units.
        day_named = {(b.unit or '').strip().lower() for b in bookings if (b.unit or '').strip()}
        day_unitless = sum(1 for b in bookings if not (b.unit or '').strip())
        day_occupied = len(day_named) + day_unitless

        resp = Response({
            'space': space.key,
            'date': date_str,
            'closed': closed,
            'business_hours': {'open': open_str, 'close': close_str},
            'slots': slots,
            'taken': taken,
            'blocked': blocked,
            'units': capacity,
            'unit_labels': space.unit_labels,
            # A full day is only bookable for an upcoming date — never today (the
            # day is already under way) or the past.
            'fullday_available': (not closed) and day > now.date() and not fullday_taken
                                 and not fullday_blocked and day_occupied < capacity,
        })
        # Availability is time-sensitive and booking-dependent — never let a browser
        # or proxy serve a stale copy.
        resp['Cache-Control'] = 'no-store'
        return resp


class BookingViewSet(viewsets.ModelViewSet):
    """CRUD for the current member's bookings, plus a cancel action."""

    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

    def get_queryset(self):
        qs = Booking.objects.filter(user=self.request.user).select_related('space')
        when = self.request.query_params.get('when')
        if when in ('upcoming', 'past', 'cancelled'):
            today = timezone.localdate()
            if when == 'cancelled':
                qs = qs.filter(status=Booking.Status.CANCELLED)
            elif when == 'upcoming':
                qs = qs.exclude(status=Booking.Status.CANCELLED).filter(date__gte=today)
            else:  # past
                qs = qs.exclude(status=Booking.Status.CANCELLED).filter(date__lt=today)
        return qs

    def get_serializer_class(self):
        if self.action == 'create':
            return BookingCreateSerializer
        return BookingSerializer

    def perform_create(self, serializer):
        booking = serializer.save()
        _send_booking_confirmation(booking)  # to the client
        _notify_owner_of_booking(booking)    # to the owner

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        booking = self.get_object()
        if booking.status == Booking.Status.CANCELLED:
            return Response({'detail': 'Booking is already cancelled.'},
                            status=status.HTTP_400_BAD_REQUEST)
        if booking.when == 'past':
            return Response({'detail': 'Past bookings cannot be cancelled.'},
                            status=status.HTTP_400_BAD_REQUEST)
        if booking.change_requested:
            return Response({'detail': 'A change request on this booking is awaiting '
                                       'review — it can\'t be cancelled until that\'s resolved.'},
                            status=status.HTTP_400_BAD_REQUEST)
        booking.status = Booking.Status.CANCELLED
        booking.save(update_fields=['status'])
        _refund_free_hours(booking)
        _send_booking_cancellation(booking)
        return Response(BookingSerializer(booking).data)

    @action(detail=True, methods=['post'], url_path='request-change')
    def request_change(self, request, pk=None):
        """Member proposes a new date/time for an existing booking. The booking is
        locked as 'change pending' and the owner is emailed to review it; nothing
        is applied until an admin approves."""
        booking = self.get_object()
        if booking.status == Booking.Status.CANCELLED:
            return Response({'detail': 'Cancelled bookings can\'t be rescheduled.'},
                            status=status.HTTP_400_BAD_REQUEST)
        if booking.when == 'past':
            return Response({'detail': 'Past bookings can\'t be rescheduled.'},
                            status=status.HTTP_400_BAD_REQUEST)
        if booking.change_requested:
            return Response({'detail': 'A change request on this booking is already '
                                       'awaiting review.'},
                            status=status.HTTP_400_BAD_REQUEST)

        new_date = _parse_date(request.data.get('date'))
        if not new_date:
            return Response({'detail': 'Pick a valid date.'},
                            status=status.HTTP_400_BAD_REQUEST)
        now = timezone.localtime()
        today = now.date()
        if new_date < today:
            return Response({'detail': 'Pick a date in the future.'},
                            status=status.HTTP_400_BAD_REQUEST)

        # A reschedule can also change the booking's shape — hourly ↔ full day and,
        # for hourly, the number of hours. Falls back to the current duration.
        space = booking.space
        duration = request.data.get('duration') or booking.duration
        if duration not in (Booking.Duration.HOURLY, Booking.Duration.FULLDAY):
            return Response({'detail': 'Choose an hourly or full-day booking.'},
                            status=status.HTTP_400_BAD_REQUEST)
        if space.durations and duration not in space.durations:
            return Response({'detail': f'{space.name} can\'t be booked "{duration}".'},
                            status=status.HTTP_400_BAD_REQUEST)

        start = end = None
        hours = None
        if duration == Booking.Duration.HOURLY:
            start = _parse_time(request.data.get('start_time'))
            if not start:
                return Response({'detail': 'Pick a start time.'},
                                status=status.HTTP_400_BAD_REQUEST)
            if new_date == today and start <= now.time():
                return Response({'detail': 'That time has already passed — pick a later slot.'},
                                status=status.HTTP_400_BAD_REQUEST)
            try:
                hours = int(request.data.get('hours') or _booking_length_hours(booking))
            except (TypeError, ValueError):
                hours = _booking_length_hours(booking)
            hours = max(1, min(12, hours))
            open_h, close_h, closed, close_str = business_window(new_date)
            if closed:
                return Response({'detail': 'The center is closed on that day.'},
                                status=status.HTTP_400_BAD_REQUEST)
            if start.hour * 60 + start.minute + hours * 60 > close_h * 60:
                return Response({'detail': f'That runs past closing ({close_str}). Reduce the hours.'},
                                status=status.HTTP_400_BAD_REQUEST)
            end = _slot_end_time(new_date, start, hours)
        else:
            # A full day that's already under way isn't a full day.
            if new_date == today:
                return Response({'detail': 'Full-day bookings must be for an upcoming day.'},
                                status=status.HTTP_400_BAD_REQUEST)

        conflict = BookingCreateSerializer._overlap_conflict(
            space, new_date, booking.unit, start, end, exclude_pk=booking.pk,
        )
        if conflict:
            return Response({'detail': conflict}, status=status.HTTP_400_BAD_REQUEST)
        blocked = BookingCreateSerializer._blocked(space, new_date, start, end)
        if blocked:
            return Response({'detail': blocked}, status=status.HTTP_400_BAD_REQUEST)

        booking.change_requested = True
        booking.requested_date = new_date
        booking.requested_start_time = start
        booking.requested_duration = duration
        booking.requested_hours = hours
        booking.save(update_fields=['change_requested', 'requested_date',
                                    'requested_start_time', 'requested_duration',
                                    'requested_hours'])
        _notify_owner_of_change_request(booking)
        return Response(BookingSerializer(booking).data)


class OrderCreateView(APIView):
    """POST /api/orders/ — place a paid checkout as one order (Whish flow).

    Validates and creates the booking(s), holds the slot(s) as pending, and returns
    the order (number + amount + Whish account) so the client can transfer and upload
    a receipt. 'Pay at center' still books directly through the booking endpoint."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        items = request.data.get('bookings') or []
        method = request.data.get('payment_method') or Order.Method.WHISH
        if not isinstance(items, list) or not items:
            return Response({'detail': 'No bookings to order.'},
                            status=status.HTTP_400_BAD_REQUEST)
        # Only Whish orders go through here — "pay at center" books directly and
        # must never create a stuck order that no one ever settles.
        if method != Order.Method.WHISH:
            return Response({'detail': 'Only Whish orders are supported here.'},
                            status=status.HTTP_400_BAD_REQUEST)

        # Validate every line up front so one bad slot aborts the whole order.
        sers = []
        for it in items:
            s = BookingCreateSerializer(data=it, context={'request': request})
            if not s.is_valid():
                return Response(s.errors, status=status.HTTP_400_BAD_REQUEST)
            sers.append(s)

        with transaction.atomic():
            order = Order.objects.create(
                user=request.user, payment_method=method, status=Order.Status.AWAITING)
            total = 0
            for s in sers:
                # create() re-checks the slot under a row lock, so a second line
                # colliding with the first (or a concurrent request) is rejected
                # and rolls back the whole order.
                booking = s.save()
                booking.order = order
                booking.is_pending = True  # hold the slot until payment is verified
                booking.save(update_fields=['order', 'is_pending'])
                total += booking.price or 0
            order.amount = total
            order.save(update_fields=['amount'])
            if total <= 0:
                # Nothing to pay (e.g. fully covered by free hours) — confirm now
                # (sets is_paid and emails the customer).
                confirm_order_paid(order)

        return Response(OrderSerializer(order, context={'request': request}).data,
                        status=status.HTTP_201_CREATED)


def confirm_order_paid(order):
    """Mark an order Paid and confirm its held bookings (emailing the customer).
    Shared by the OCR auto-verify path and the admin Mark-paid action."""
    order.status = Order.Status.PAID
    order.paid_at = timezone.now()
    order.save(update_fields=['status', 'paid_at'])
    for b in order.bookings.exclude(status=Booking.Status.CANCELLED):
        b.is_pending = False
        b.is_paid = True
        b.save(update_fields=['is_pending', 'is_paid'])
        _send_booking_confirmation(b)


class OrderDetailView(APIView):
    """GET /api/orders/<order_number>/ — the customer's own order (payment page)."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, order_number):
        order = Order.objects.filter(order_number=order_number, user=request.user).first()
        if not order:
            return Response({'detail': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(OrderSerializer(order, context={'request': request}).data)


def _content_matches_ext(fileobj, ext):
    """Sniff the file's magic bytes so a mislabeled/polyglot file (e.g. HTML named
    .png) can't be stored and served from same-origin /media."""
    fileobj.seek(0)
    head = fileobj.read(12)
    fileobj.seek(0)
    checks = {
        '.jpg': head[:3] == b'\xff\xd8\xff',
        '.jpeg': head[:3] == b'\xff\xd8\xff',
        '.png': head[:8] == b'\x89PNG\r\n\x1a\n',
        '.gif': head[:6] in (b'GIF87a', b'GIF89a'),
        '.webp': head[:4] == b'RIFF' and head[8:12] == b'WEBP',
        '.pdf': head[:5] == b'%PDF-',
    }
    return checks.get(ext, False)


class OrderReceiptView(APIView):
    """POST /api/orders/<order_number>/receipt/ — upload the Whish transfer receipt."""

    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    ALLOWED = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.pdf'}
    MAX = 8 * 1024 * 1024

    def post(self, request, order_number):
        order = Order.objects.filter(order_number=order_number, user=request.user).first()
        if not order:
            return Response({'detail': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)
        if order.status == Order.Status.PAID:
            return Response({'detail': 'This order is already paid.'},
                            status=status.HTTP_400_BAD_REQUEST)
        f = request.FILES.get('file')
        if not f:
            return Response({'detail': 'Attach your payment receipt.'},
                            status=status.HTTP_400_BAD_REQUEST)
        ext = os.path.splitext(f.name)[1].lower()
        if ext not in self.ALLOWED:
            return Response({'detail': 'Upload an image or PDF.'},
                            status=status.HTTP_400_BAD_REQUEST)
        if not _content_matches_ext(f, ext):
            return Response({'detail': 'That file doesn\'t look like a valid image or PDF.'},
                            status=status.HTTP_400_BAD_REQUEST)
        if f.size > self.MAX:
            return Response({'detail': 'File too large (max 8MB).'},
                            status=status.HTTP_400_BAD_REQUEST)
        path = default_storage.save(f'receipts/{uuid.uuid4().hex}{ext}', f)
        order.receipt_url = default_storage.url(path)
        order.status = Order.Status.SUBMITTED
        order.save(update_fields=['receipt_url', 'status'])
        return Response(OrderSerializer(order, context={'request': request}).data)


class OverviewView(APIView):
    """GET /api/overview/ — dashboard summary for the logged-in member."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        today = timezone.localdate()

        membership = Membership.objects.filter(user=user).select_related('plan').first()
        if membership:
            membership.sync_period()  # lazy monthly reset before reading balances
        bookings = Booking.objects.filter(user=user).select_related('space')

        this_month = bookings.exclude(status=Booking.Status.CANCELLED).filter(
            date__year=today.year, date__month=today.month
        ).count()

        upcoming = bookings.exclude(status=Booking.Status.CANCELLED).filter(
            date__gte=today
        ).order_by('date', 'start_time')[:3]

        stats = {
            'this_month': this_month,
            'room_hours_left': membership.room_hours_left if membership else 0,
            'guest_passes_left': membership.guest_passes_left if membership else 0,
            'member_since': membership.member_since.year if membership else user.date_joined.year,
        }

        return Response({
            'membership': MembershipSerializer(membership).data if membership else None,
            'stats': stats,
            'upcoming': BookingSerializer(upcoming, many=True).data,
        })


class ScheduleChangeView(APIView):
    """POST /api/schedule-change/ — a member proposes an edit to their package
    schedule (which package covers which days). The proposal is stored as pending
    and the owner is emailed; nothing changes until an admin approves."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        membership = (Membership.objects.filter(user=request.user)
                      .select_related('plan').first())
        if not membership:
            return Response({'detail': 'You don\'t have a membership to edit.'},
                            status=status.HTTP_400_BAD_REQUEST)
        if membership.schedule_change_requested:
            return Response({'detail': 'You already have a schedule change awaiting review.'},
                            status=status.HTTP_400_BAD_REQUEST)

        # The member may only reallocate days among the dated packages they already
        # have — lifetime packages are fixed, and they can't add new packages.
        editable = membership.editable_components
        if not editable:
            return Response({'detail': 'Your package has no editable schedule to change.'},
                            status=status.HTTP_400_BAD_REQUEST)
        allowed = {c.get('name'): c for c in editable if c.get('name')}
        # Days already in the member's schedule are immutable history — carrying
        # them through (even if now in the past) must not be rejected. Only brand
        # new past days the member tries to add are blocked.
        existing_dates = {str(d) for c in editable for d in (c.get('dates') or [])}

        proposed = request.data.get('components')
        if not isinstance(proposed, list):
            return Response({'detail': 'Send the packages and their days.'},
                            status=status.HTTP_400_BAD_REQUEST)

        seen_dates = set()
        dated = []
        today = timezone.localdate()
        for c in proposed:
            if not isinstance(c, dict):
                continue
            name = str(c.get('name') or '').strip()
            base = allowed.get(name)
            if not base:
                label = name or 'That package'
                return Response({'detail': f'"{label}" isn\'t part of your package.'},
                                status=status.HTTP_400_BAD_REQUEST)
            days = []
            for d in (c.get('dates') or []):
                parsed = _parse_date(str(d))
                if not parsed:
                    return Response({'detail': 'One of the selected days is invalid.'},
                                    status=status.HTTP_400_BAD_REQUEST)
                iso = parsed.isoformat()
                if parsed < today and iso not in existing_dates:
                    return Response({'detail': 'You can\'t assign new days in the past.'},
                                    status=status.HTTP_400_BAD_REQUEST)
                if iso in seen_dates:
                    return Response({'detail': 'Each day can belong to only one package.'},
                                    status=status.HTTP_400_BAD_REQUEST)
                seen_dates.add(iso)
                days.append(iso)
            entry = {'name': name, 'dates': sorted(days), 'quantity': len(days)}
            if base.get('plan') is not None:
                entry['plan'] = base['plan']
            dated.append(entry)

        # Preserve the member's lifetime packages exactly; only the dated ones change.
        lifetime = [c for c in (membership.custom_components or [])
                    if isinstance(c, dict) and c.get('lifetime')]
        membership.pending_components = lifetime + dated
        membership.schedule_change_requested = True
        membership.save(update_fields=['pending_components', 'schedule_change_requested'])
        _notify_owner_of_schedule_change(membership)
        return Response(MembershipSerializer(membership).data)


# ----- helpers -----

def _parse_hour(value, fallback):
    """Parse an 'HH:MM' string to an integer hour, falling back on bad input."""
    try:
        return int(str(value).split(':')[0])
    except (ValueError, AttributeError, IndexError):
        return fallback


def _parse_date(value):
    """Parse a 'YYYY-MM-DD' string to a date, or None."""
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except ValueError:
        return None


def _parse_time(value):
    """Parse an 'HH:MM' (or 'HH:MM:SS') string to a time, or None."""
    if not value:
        return None
    for fmt in ('%H:%M', '%H:%M:%S'):
        try:
            return datetime.strptime(str(value), fmt).time()
        except ValueError:
            continue
    return None


def _slot_end_time(day, start, hours):
    """The end time `hours` after `start` on `day`."""
    return (datetime.combine(day, start) + timedelta(hours=hours)).time()


def _booking_length_hours(booking):
    """How many hours an hourly booking spans (defaults to 1)."""
    if booking.start_time and booking.end_time:
        start = datetime.combine(date.today(), booking.start_time)
        end = datetime.combine(date.today(), booking.end_time)
        hours = round((end - start).total_seconds() / 3600)
        return max(1, hours)
    return 1


def _send_booking_confirmation(booking):
    """Email the member a confirmation of their booking (console backend)."""
    from django.conf import settings as dj_settings
    from django.core.mail import send_mail

    user = booking.user
    if not user.email:
        return
    when = 'Full day'
    if booking.duration == Booking.Duration.HOURLY and booking.start_time:
        when = booking.start_time.strftime('%H:%M')
        if booking.end_time:
            when += f' – {booking.end_time.strftime("%H:%M")}'
    unit = f' · {booking.unit}' if booking.unit else ''
    body = (
        f'Hi {user.full_name},\n\n'
        f'Your booking is confirmed.\n\n'
        f'Space: {booking.space.name}{unit}\n'
        f'Date:  {booking.date:%A, %d %b %Y}\n'
        f'Time:  {when}\n'
        + (f'Attendees: {booking.attendees}\n' if booking.attendees else '')
        + '\nSee you at the center!\n'
    )
    try:
        send_mail(
            subject=f'Booking confirmed — {booking.space.name} on {booking.date:%d %b}',
            message=body,
            from_email=dj_settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
        )
    except Exception:
        pass


def _notify_owner_of_booking(booking):
    """Email the site owner that a client booked a space (console backend)."""
    from django.conf import settings as dj_settings
    from django.core.mail import send_mail

    recipient = (AdminSettings.load().notification_email
                 or getattr(dj_settings, 'OWNER_EMAIL', '') or dj_settings.DEFAULT_FROM_EMAIL)
    if not recipient:
        return
    user = booking.user
    when = 'Full day'
    if booking.duration == Booking.Duration.HOURLY and booking.start_time:
        when = booking.start_time.strftime('%H:%M')
        if booking.end_time:
            when += f' – {booking.end_time.strftime("%H:%M")}'
    unit = f' · {booking.unit}' if booking.unit else ''
    pay = 'Free with plan' if booking.is_free else 'Pay at center'
    body = (
        f'{user.full_name} booked {booking.space.name}{unit}.\n\n'
        f'Client: {user.full_name} ({user.email})\n'
        f'Space:  {booking.space.name}{unit}\n'
        f'Date:   {booking.date:%A, %d %b %Y}\n'
        f'Time:   {when}\n'
        + (f'Attendees: {booking.attendees}\n' if booking.attendees else '')
        + f'Payment: {pay}\n'
    )
    try:
        send_mail(
            subject=f'New booking — {booking.space.name} by {user.full_name}',
            message=body,
            from_email=dj_settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=True,
        )
    except Exception:
        pass


def _describe_slot(booking, when_date, start):
    """A one-line 'Mon, 08 Aug 2026 · 14:00' description of a booking slot."""
    line = f'{when_date:%A, %d %b %Y}'
    if booking.duration == Booking.Duration.HOURLY and start:
        line += f' · {start.strftime("%H:%M")}'
    else:
        line += ' · Full day'
    return line


def _notify_owner_of_change_request(booking):
    """Email the owner that a member wants to reschedule a booking (console backend)."""
    from django.conf import settings as dj_settings
    from django.core.mail import send_mail

    recipient = (AdminSettings.load().notification_email
                 or getattr(dj_settings, 'OWNER_EMAIL', '') or dj_settings.DEFAULT_FROM_EMAIL)
    if not recipient:
        return
    user = booking.user
    unit = f' · {booking.unit}' if booking.unit else ''
    current = _describe_slot(booking, booking.date, booking.start_time)
    requested = _describe_slot(booking, booking.requested_date, booking.requested_start_time)
    body = (
        f'{user.full_name} requested a change to their booking of '
        f'{booking.space.name}{unit}.\n\n'
        f'Client:  {user.full_name} ({user.email})\n'
        f'Space:   {booking.space.name}{unit}\n\n'
        f'Current:   {current}\n'
        f'Requested: {requested}\n\n'
        f'Review it in the admin panel under Daily Bookings → Change requests to '
        f'approve or reject.\n'
    )
    try:
        send_mail(
            subject=f'Booking change request — {booking.space.name} by {user.full_name}',
            message=body,
            from_email=dj_settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=True,
        )
    except Exception:
        pass


def _send_change_result(booking, approved):
    """Email the member the outcome of their reschedule request (best-effort)."""
    from django.conf import settings as dj_settings
    from django.core.mail import send_mail

    user = booking.user
    if not user.email:
        return
    unit = f' · {booking.unit}' if booking.unit else ''
    slot = _describe_slot(booking, booking.date, booking.start_time)
    if approved:
        subject = f'Booking rescheduled — {booking.space.name} on {booking.date:%d %b}'
        body = (
            f'Hi {user.full_name},\n\n'
            f'Your reschedule request was approved.\n\n'
            f'Space: {booking.space.name}{unit}\n'
            f'New booking: {slot}\n\n'
            f'See you at the center!\n'
        )
    else:
        subject = f'Reschedule request declined — {booking.space.name}'
        body = (
            f'Hi {user.full_name},\n\n'
            f'We couldn\'t apply your requested change, so your booking is unchanged:\n\n'
            f'Space: {booking.space.name}{unit}\n'
            f'Booking: {slot}\n\n'
            f'Feel free to submit a new request or contact us for help.\n'
        )
    try:
        send_mail(
            subject=subject, message=body,
            from_email=dj_settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email], fail_silently=True,
        )
    except Exception:
        pass


def _schedule_breakdown(components):
    """Human-readable 'package — N day(s): dates' lines for an allocation."""
    lines = []
    for c in components or []:
        if not isinstance(c, dict):
            continue
        name = c.get('name') or 'Package'
        if c.get('lifetime'):
            lines.append(f'  • {name} — lifetime')
            continue
        dates = sorted(c.get('dates') or [])
        if not dates:
            continue
        shown = f'{dates[0]} → {dates[-1]}' if len(dates) > 10 else ', '.join(dates)
        lines.append(f'  • {name} — {len(dates)} day(s): {shown}')
    return '\n'.join(lines) or '  —'


def _notify_owner_of_schedule_change(membership):
    """Email the owner that a member proposed a package-schedule edit (console backend)."""
    from django.conf import settings as dj_settings
    from django.core.mail import send_mail

    recipient = (AdminSettings.load().notification_email
                 or getattr(dj_settings, 'OWNER_EMAIL', '') or dj_settings.DEFAULT_FROM_EMAIL)
    if not recipient:
        return
    user = membership.user
    body = (
        f'{user.full_name} requested changes to their package schedule.\n\n'
        f'Client:  {user.full_name} ({user.email})\n'
        f'Package: {membership.display_name}\n\n'
        f'Current schedule:\n{_schedule_breakdown(membership.custom_components)}\n\n'
        f'Requested schedule:\n{_schedule_breakdown(membership.pending_components)}\n\n'
        f'Review it in the admin panel under Users to approve or reject.\n'
    )
    try:
        send_mail(
            subject=f'Schedule change request — {user.full_name}',
            message=body,
            from_email=dj_settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=True,
        )
    except Exception:
        pass


def _send_schedule_change_result(membership, approved):
    """Email the member the outcome of their schedule-change request (best-effort)."""
    from django.conf import settings as dj_settings
    from django.core.mail import send_mail

    user = membership.user
    if not user.email:
        return
    if approved:
        subject = 'Your package schedule was updated'
        body = (
            f'Hi {user.full_name},\n\n'
            f'Your requested schedule change was approved and is now live.\n\n'
            f'Package: {membership.display_name}\n'
            f'Schedule:\n{_schedule_breakdown(membership.custom_components)}\n\n'
            f'You can see it any time in your dashboard.\n'
        )
    else:
        subject = 'Schedule change request declined'
        body = (
            f'Hi {user.full_name},\n\n'
            f'We couldn\'t apply your requested schedule change, so your package is '
            f'unchanged:\n\n'
            f'Package: {membership.display_name}\n'
            f'Schedule:\n{_schedule_breakdown(membership.custom_components)}\n\n'
            f'Feel free to submit a new request or contact us for help.\n'
        )
    try:
        send_mail(
            subject=subject, message=body,
            from_email=dj_settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email], fail_silently=True,
        )
    except Exception:
        pass


def _send_booking_cancellation(booking):
    """Email the member confirming their booking was cancelled (best-effort)."""
    from django.conf import settings as dj_settings
    from django.core.mail import send_mail

    user = booking.user
    if not user.email:
        return
    unit = f' · {booking.unit}' if booking.unit else ''
    body = (
        f'Hi {user.full_name},\n\n'
        f'Your booking has been cancelled.\n\n'
        f'Space: {booking.space.name}{unit}\n'
        f'Date:  {booking.date:%A, %d %b %Y}\n\n'
        + ('Any free meeting-room hours used have been returned to your balance.\n'
           if booking.space.uses_free_hours else '')
        + '\nHope to see you again soon.\n'
    )
    try:
        send_mail(
            subject=f'Booking cancelled — {booking.space.name} on {booking.date:%d %b}',
            message=body,
            from_email=dj_settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True,
        )
    except Exception:
        pass


def _refund_free_hours(booking):
    """Return free meeting-room hours to a member when a booking is cancelled."""
    if not booking.free_hours_used:
        return
    membership = Membership.objects.filter(user=booking.user).select_related('plan').first()
    if not membership:
        return
    membership.sync_period()
    membership.room_hours_used = max(
        0, float(membership.room_hours_used) - float(booking.free_hours_used)
    )
    membership.save(update_fields=['room_hours_used', 'hours_period'])
    booking.free_hours_used = 0
    booking.save(update_fields=['free_hours_used'])


class NotEnoughHoursError(Exception):
    """Raised when a reschedule needs more free meeting-room hours than the member has."""

    def __init__(self, left, needed):
        self.left, self.needed = left, needed
        super().__init__(f'Not enough free meeting-room hours ({left:g} left, {needed} needed).')


def apply_booking_change(booking, new_date, duration, start, end, hours):
    """Move/resize a booking and re-settle its price + free meeting-room hours.

    Refunds whatever free hours the booking currently holds, then re-deducts for
    the new shape (hourly on a free-hours space), recomputing is_free/price. Raises
    NotEnoughHoursError if the member's balance can't cover the new hourly length.
    Runs atomically so a shortfall leaves the booking (and balance) untouched.
    """
    from .models import Booking, Membership

    space = booking.space
    with transaction.atomic():
        _refund_free_hours(booking)  # return the old allocation to the member's balance

        deducted = 0
        if duration == Booking.Duration.HOURLY and space.uses_free_hours:
            membership = (Membership.objects.select_for_update()
                          .filter(user=booking.user).select_related('plan').first())
            if membership:
                membership.sync_period()
                if membership.room_hours_left < hours:
                    raise NotEnoughHoursError(membership.room_hours_left, hours)
                membership.room_hours_used = float(membership.room_hours_used) + hours
                membership.save(update_fields=['room_hours_used', 'hours_period'])
                deducted = hours

        booking.date = new_date
        booking.duration = duration
        booking.start_time = start
        booking.end_time = end
        booking.free_hours_used = deducted

        if deducted or space.is_free:
            booking.is_free = True
            booking.price = None
        elif duration == Booking.Duration.HOURLY:
            rate = space.hour_price if space.hour_price is not None else space.day_price
            booking.is_free = False
            booking.price = (rate or 0) * hours
        else:
            booking.is_free = False
            booking.price = space.day_price

        booking.change_requested = False
        booking.requested_date = None
        booking.requested_start_time = None
        booking.requested_duration = None
        booking.requested_hours = None
        booking.save()


def _notify_owner_of_tour(tour):
    """Email the site owner about a new Book-a-Tour submission (console backend)."""
    from django.conf import settings as dj_settings
    from django.core.mail import send_mail

    recipient = (AdminSettings.load().notification_email
                 or getattr(dj_settings, 'OWNER_EMAIL', '') or dj_settings.DEFAULT_FROM_EMAIL)
    promo = tour.promo_code_text or '—'
    body = (
        f'{tour.full_name} requested a tour of the coworking space.\n\n'
        f'Name:  {tour.full_name}\n'
        f'Email: {tour.email}\n'
        f'Phone: {tour.phone}\n'
        f'Promo code: {promo}\n'
    )
    try:
        send_mail(
            subject=f'New tour request — {tour.full_name}',
            message=body,
            from_email=dj_settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=True,
        )
    except Exception:
        # Never let a mail failure block the tour submission.
        pass


def _notify_owner_of_customization(data):
    """Email the site owner about a 'customize my package' enquiry (console backend)."""
    from django.conf import settings as dj_settings
    from django.core.mail import send_mail

    recipient = (AdminSettings.load().notification_email
                 or getattr(dj_settings, 'OWNER_EMAIL', '') or dj_settings.DEFAULT_FROM_EMAIL)
    details = (data.get('details') or '').strip()
    items = data.get('items') or []
    total_days = 0
    lines = []
    for it in items:
        dates = sorted(it.get('dates') or [])
        iso = [d.isoformat() if hasattr(d, 'isoformat') else str(d) for d in dates]
        total_days += len(iso)
        shown = f'{iso[0]} → {iso[-1]}' if len(iso) > 10 else ', '.join(iso)
        # Optional time of day: full day (default) or a specific start + hours.
        if (it.get('duration') or 'fullday') == 'hourly' and it.get('start_time'):
            st = it['start_time']
            st = st.strftime('%H:%M') if hasattr(st, 'strftime') else str(st)
            when = f'{st} · {it.get("hours") or 1} hr(s)'
        else:
            when = 'Full day'
        lines.append(f"  • {it['office']} [{when}] — {len(iso)} day(s): {shown}")
    breakdown = '\n'.join(lines) or '  —'
    body = (
        f"{data['name']} wants to build a custom package.\n\n"
        f"Name:  {data['name']}\n"
        f"Email: {data['email']}\n"
        f"Phone: {data.get('phone') or '—'}\n\n"
        f"Custom package ({total_days} day(s) across {len(items)} office type(s)):\n"
        f"{breakdown}\n"
        f"\nDetails:\n{details or '—'}\n"
    )
    try:
        send_mail(
            subject=f"Package customization request — {data['name']}",
            message=body,
            from_email=dj_settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=True,
        )
    except Exception:
        # Never let a mail failure block the customization submission.
        pass
