import os
import uuid
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework.exceptions import MethodNotAllowed

from accounts.emails import send_account_approved, send_password_reset
from accounts.permissions import IsAdminRole
from bookings.models import (
    AdminSettings, BlockedSlot, Booking, CustomizationRequest, FAQ, GalleryImage,
    Membership, MembershipPlan, PackageCategory, PromoCode, SiteContent, Space,
    TourRequest,
)
from bookings.serializers import (
    BookingCreateSerializer, FAQSerializer, GalleryImageSerializer, MONTHS,
)
from bookings.views import (
    _booking_length_hours, _send_change_result, _send_schedule_change_result,
    _slot_end_time,
)

from .serializers import (
    AdminPackageCategorySerializer,
    AdminSettingsSerializer,
    AdminSpaceSerializer,
    AdminUserSerializer,
    BlockedSlotSerializer,
    ClientSerializer,
    CustomizationRequestSerializer,
    PackageSerializer,
    PromoCodeSerializer,
    ReservationEditSerializer,
    ReservationSerializer,
    SiteContentSerializer,
    TourRequestSerializer,
)

User = get_user_model()


def _money(amount):
    amount = float(amount or 0)
    if amount >= 1000:
        return f'${amount / 1000:.1f}k'
    return f'${amount:.0f}'


def _ago(dt):
    secs = (timezone.now() - dt).total_seconds()
    if secs < 3600:
        return f'{int(secs // 60)}m ago'
    if secs < 86400:
        return f'{int(secs // 3600)}h ago'
    return f'{int(secs // 86400)}d ago'


# ----- Users / clients -----

class AdminUserViewSet(viewsets.ModelViewSet):
    """Member accounts: list, approve, reject."""

    serializer_class = AdminUserSerializer
    permission_classes = [IsAdminRole]
    # 'post' stays enabled for the detail @action routes (approve, reject, …);
    # direct user creation is intentionally disabled (see create()).
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

    def create(self, request, *args, **kwargs):
        # Users self-register via /api/auth/register/. Admin-side creation isn't
        # supported (the serializer is read-only) — reject cleanly instead of 500.
        raise MethodNotAllowed('POST')

    def get_queryset(self):
        qs = User.objects.all().select_related('membership__plan')
        s = self.request.query_params.get('status')
        if s == 'pending':
            qs = qs.filter(is_approved=False, is_active=True)
        elif s == 'approved':
            qs = qs.filter(is_approved=True)
        elif s == 'members':
            qs = qs.filter(role=User.Role.MEMBER)
        return qs

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        user = self.get_object()
        was_approved = user.is_approved
        user.is_approved = True
        user.is_active = True
        user.save(update_fields=['is_approved', 'is_active'])
        if not was_approved:
            send_account_approved(user)  # welcome / you-can-log-in-now email
        return Response(self.get_serializer(user).data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        user = self.get_object()
        user.is_approved = False
        user.is_active = False
        user.save(update_fields=['is_approved', 'is_active'])
        return Response(self.get_serializer(user).data)

    @action(detail=True, methods=['post'], url_path='set-active')
    def set_active(self, request, pk=None):
        """Activate or deactivate an account. Body: {"is_active": bool} (optional; toggles if omitted)."""
        user = self.get_object()
        value = request.data.get('is_active')
        user.is_active = (not user.is_active) if value is None else bool(value)
        user.save(update_fields=['is_active'])
        return Response(self.get_serializer(user).data)

    @action(detail=True, methods=['post'], url_path='reset-password')
    def reset_password(self, request, pk=None):
        """Email the member a one-time password-reset link.

        We deliberately do NOT set or return a cleartext password: emailing a
        live password (and echoing it in the response) exposes it in inboxes,
        logs and proxies. The member sets their own password via the link.
        """
        user = self.get_object()
        send_password_reset(user)
        return Response({'id': user.id, 'email': user.email,
                         'detail': 'A password-reset link has been emailed to the member.'})

    @action(detail=True, methods=['post'], url_path='set-hours')
    def set_hours(self, request, pk=None):
        """Adjust a member's monthly free hours / current usage.

        Body: {"monthly_hours": int|null, "room_hours_used": number} (both optional).
        """
        user = self.get_object()
        membership = Membership.objects.filter(user=user).select_related('plan').first()
        if not membership:
            return Response({'detail': 'This user has no membership.'},
                            status=status.HTTP_400_BAD_REQUEST)
        membership.sync_period()
        if 'monthly_hours' in request.data:
            mh = request.data.get('monthly_hours')
            membership.monthly_hours = None if mh in (None, '') else int(mh)
        if 'room_hours_used' in request.data:
            membership.room_hours_used = max(0, float(request.data.get('room_hours_used') or 0))
        membership.save(update_fields=['monthly_hours', 'room_hours_used', 'hours_period'])
        return Response({
            'id': user.id,
            'monthly_hours': membership.monthly_hours,
            'effective_hours': membership.effective_hours,
            'room_hours_used': float(membership.room_hours_used),
            'room_hours_left': membership.room_hours_left,
        })

    @staticmethod
    def _membership_detail(user, membership):
        """Shape a membership for the admin Customize modal (or nulls if none)."""
        if not membership:
            return {'id': user.id, 'has_membership': False, 'membership': None}
        return {
            'id': user.id,
            'has_membership': True,
            'membership': {
                'plan': membership.plan_id,
                'plan_name': membership.plan.name,
                'custom_plan_name': membership.custom_plan_name,
                'display_name': membership.display_name,
                'status': membership.status,
                'monthly_hours': membership.monthly_hours,
                'effective_hours': membership.effective_hours,
                'room_hours_used': float(membership.room_hours_used),
                'room_hours_left': membership.room_hours_left,
                'custom_components': membership.custom_components or [],
                'custom_price': (None if membership.custom_price is None
                                 else float(membership.custom_price)),
                'custom_price_label': membership.custom_price_label,
                'price_display': membership.price_display,
                'is_custom': membership.is_custom,
                'member_since': membership.member_since,
                'schedule_change_requested': membership.schedule_change_requested,
                'pending_components': membership.pending_components,
            },
        }

    @action(detail=True, methods=['get'])
    def membership(self, request, pk=None):
        """Current membership detail for prefilling the Customize modal."""
        user = self.get_object()
        ms = Membership.objects.filter(user=user).select_related('plan').first()
        return Response(self._membership_detail(user, ms))

    @action(detail=True, methods=['post'], url_path='set-membership')
    def set_membership(self, request, pk=None):
        """Create or update a member's (optionally bespoke) package.

        Body: {
          "plan": <plan id, required>, "status": "active|paused|cancelled",
          "monthly_hours": int|null, "custom_components": [{service, quantity}, ...],
          "custom_price": number|null, "custom_price_label": "Custom"
        }
        """
        user = self.get_object()
        data = request.data or {}

        plan_id = data.get('plan')
        if not plan_id:
            return Response({'detail': 'A base plan is required.'},
                            status=status.HTTP_400_BAD_REQUEST)
        plan = MembershipPlan.objects.filter(pk=plan_id).first()
        if not plan:
            return Response({'detail': 'That plan does not exist.'},
                            status=status.HTTP_400_BAD_REQUEST)

        defaults = {'plan': plan}
        if 'status' in data and data['status']:
            defaults['status'] = data['status']
        if 'monthly_hours' in data:
            mh = data.get('monthly_hours')
            defaults['monthly_hours'] = None if mh in (None, '') else int(mh)
        if 'custom_components' in data:
            comps = data.get('custom_components') or []
            # Each component is a package allocated to a set of days:
            # {"plan": <id>, "name": str, "dates": [YYYY-MM-DD, ...]}.
            # Legacy free-form rows ({"service", "quantity"}) are still accepted.
            cleaned = []
            for c in comps:
                if not isinstance(c, dict):
                    continue
                name = str(c.get('name') or c.get('service') or '').strip()
                dates = c.get('dates') if isinstance(c.get('dates'), list) else []
                dates = [str(d) for d in dates if d]
                is_lifetime = bool(c.get('lifetime'))
                if not name and not dates and not is_lifetime:
                    continue
                entry = {'name': name, 'dates': dates,
                         'quantity': len(dates) if dates else c.get('quantity')}
                if is_lifetime:
                    entry['lifetime'] = True
                try:
                    if c.get('plan') not in (None, ''):
                        entry['plan'] = int(c['plan'])
                except (TypeError, ValueError):
                    pass
                cleaned.append(entry)
            defaults['custom_components'] = cleaned
        if 'custom_price' in data:
            cp = data.get('custom_price')
            defaults['custom_price'] = None if cp in (None, '') else cp
        if 'custom_price_label' in data:
            defaults['custom_price_label'] = str(data.get('custom_price_label') or '').strip()
        if 'custom_plan_name' in data:
            defaults['custom_plan_name'] = str(data.get('custom_plan_name') or '').strip()

        membership, created = Membership.objects.get_or_create(
            user=user, defaults={**defaults, 'hours_period': timezone.localdate().strftime('%Y-%m')},
        )
        if not created:
            for field, value in defaults.items():
                setattr(membership, field, value)
            membership.save()
        membership = Membership.objects.select_related('plan').get(pk=membership.pk)
        return Response(self._membership_detail(user, membership),
                        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='approve-schedule-change')
    def approve_schedule_change(self, request, pk=None):
        """Apply a member's proposed package schedule to their membership."""
        user = self.get_object()
        ms = Membership.objects.filter(user=user).select_related('plan').first()
        if not ms or not ms.has_schedule_change:
            return Response({'detail': 'This member has no pending schedule change.'},
                            status=status.HTTP_400_BAD_REQUEST)
        ms.custom_components = ms.pending_components or []
        ms.pending_components = None
        ms.schedule_change_requested = False
        ms.save(update_fields=['custom_components', 'pending_components',
                               'schedule_change_requested'])
        _send_schedule_change_result(ms, approved=True)
        return Response(self._membership_detail(user, ms))

    @action(detail=True, methods=['post'], url_path='reject-schedule-change')
    def reject_schedule_change(self, request, pk=None):
        """Discard a member's proposed package schedule; membership is unchanged."""
        user = self.get_object()
        ms = Membership.objects.filter(user=user).select_related('plan').first()
        if not ms or not ms.has_schedule_change:
            return Response({'detail': 'This member has no pending schedule change.'},
                            status=status.HTTP_400_BAD_REQUEST)
        ms.pending_components = None
        ms.schedule_change_requested = False
        ms.save(update_fields=['pending_components', 'schedule_change_requested'])
        _send_schedule_change_result(ms, approved=False)
        return Response(self._membership_detail(user, ms))


class AdminClientViewSet(viewsets.ReadOnlyModelViewSet):
    """Active clients (approved members) for the Clients table."""

    serializer_class = ClientSerializer
    permission_classes = [IsAdminRole]

    def get_queryset(self):
        return (User.objects.filter(role=User.Role.MEMBER, is_approved=True)
                .select_related('membership__plan'))


# ----- Reservations -----

class AdminReservationViewSet(viewsets.ModelViewSet):
    """All bookings across members, with approve / edit / cancel / payment toggle."""

    permission_classes = [IsAdminRole]
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_queryset(self):
        qs = Booking.objects.all().select_related('space', 'user')
        f = self.request.query_params.get('filter')
        today = date.today()
        if f == 'pending':
            qs = qs.filter(is_pending=True, status=Booking.Status.CONFIRMED)
        elif f == 'change':
            qs = qs.filter(change_requested=True, status=Booking.Status.CONFIRMED)
        elif f == 'confirmed':
            qs = qs.filter(is_pending=False, status=Booking.Status.CONFIRMED, date__gte=today)
        elif f == 'cancelled':
            qs = qs.filter(status=Booking.Status.CANCELLED)
        elif f == 'past':
            qs = qs.exclude(status=Booking.Status.CANCELLED).filter(date__lt=today)
        return qs

    def get_serializer_class(self):
        if self.action in ('partial_update', 'update'):
            return ReservationEditSerializer
        return ReservationSerializer

    def update(self, request, *args, **kwargs):
        super().update(request, *args, **kwargs)
        booking = self.get_object()
        return Response(ReservationSerializer(booking).data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        booking = self.get_object()
        booking.is_pending = False
        booking.status = Booking.Status.CONFIRMED
        booking.save(update_fields=['is_pending', 'status'])
        return Response(ReservationSerializer(booking).data)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        booking = self.get_object()
        booking.status = Booking.Status.CANCELLED
        booking.save(update_fields=['status'])
        return Response(ReservationSerializer(booking).data)

    @action(detail=True, methods=['post'], url_path='toggle-paid')
    def toggle_paid(self, request, pk=None):
        booking = self.get_object()
        booking.is_paid = not booking.is_paid
        booking.save(update_fields=['is_paid'])
        return Response(ReservationSerializer(booking).data)

    @action(detail=True, methods=['post'], url_path='approve-change')
    def approve_change(self, request, pk=None):
        """Apply a member's pending reschedule to the booking. Re-checks
        availability at approval time in case the new slot was taken meanwhile."""
        booking = self.get_object()
        if not booking.change_requested or not booking.requested_date:
            return Response({'detail': 'This booking has no pending change request.'},
                            status=status.HTTP_400_BAD_REQUEST)

        new_date = booking.requested_date
        start = end = None
        if booking.duration == Booking.Duration.HOURLY:
            start = booking.requested_start_time
            end = _slot_end_time(new_date, start, _booking_length_hours(booking))

        conflict = BookingCreateSerializer._overlap_conflict(
            booking.space, new_date, booking.unit, start, end, exclude_pk=booking.pk,
        )
        if conflict:
            return Response({'detail': f'Can\'t approve — {conflict}'},
                            status=status.HTTP_400_BAD_REQUEST)
        blocked = BookingCreateSerializer._blocked(booking.space, new_date, start, end)
        if blocked:
            return Response({'detail': f'Can\'t approve — {blocked}'},
                            status=status.HTTP_400_BAD_REQUEST)

        booking.date = new_date
        booking.start_time = start
        booking.end_time = end
        booking.change_requested = False
        booking.requested_date = None
        booking.requested_start_time = None
        booking.save(update_fields=[
            'date', 'start_time', 'end_time',
            'change_requested', 'requested_date', 'requested_start_time',
        ])
        _send_change_result(booking, approved=True)
        return Response(ReservationSerializer(booking).data)

    @action(detail=True, methods=['post'], url_path='reject-change')
    def reject_change(self, request, pk=None):
        """Discard a member's pending reschedule; the booking is left unchanged."""
        booking = self.get_object()
        if not booking.change_requested:
            return Response({'detail': 'This booking has no pending change request.'},
                            status=status.HTTP_400_BAD_REQUEST)
        booking.change_requested = False
        booking.requested_date = None
        booking.requested_start_time = None
        booking.save(update_fields=[
            'change_requested', 'requested_date', 'requested_start_time',
        ])
        _send_change_result(booking, approved=False)
        return Response(ReservationSerializer(booking).data)


# ----- Spaces & packages -----

class AdminSpaceViewSet(viewsets.ModelViewSet):
    serializer_class = AdminSpaceSerializer
    permission_classes = [IsAdminRole]
    queryset = Space.objects.all()

    def destroy(self, request, *args, **kwargs):
        space = self.get_object()
        # Bookings PROTECT the space; give the admin a clear reason instead of a 500.
        if space.bookings.exists():
            return Response(
                {'detail': 'This space has bookings and can’t be deleted. '
                           'Deactivate it instead to hide it from members.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['post'], url_path='toggle-active')
    def toggle_active(self, request, pk=None):
        space = self.get_object()
        space.is_active = not space.is_active
        space.save(update_fields=['is_active'])
        return Response(self.get_serializer(space).data)


class AdminPackageCategoryViewSet(viewsets.ModelViewSet):
    """CRUD for unlimited, admin-managed package categories."""

    serializer_class = AdminPackageCategorySerializer
    permission_classes = [IsAdminRole]
    queryset = PackageCategory.objects.all()


class AdminPackageViewSet(viewsets.ModelViewSet):
    serializer_class = PackageSerializer
    permission_classes = [IsAdminRole]

    def get_queryset(self):
        qs = MembershipPlan.objects.all().select_related('category')
        if self.request.query_params.get('include_archived') not in ('1', 'true', 'yes'):
            qs = qs.filter(is_archived=False)
        return qs

    @action(detail=True, methods=['post'])
    def duplicate(self, request, pk=None):
        plan = self.get_object()
        clone = MembershipPlan.objects.get(pk=plan.pk)
        clone.pk = None
        clone.name = f'{plan.name} (copy)'[:80]
        clone.is_archived = False
        clone.featured = False
        clone.save()
        return Response(self.get_serializer(clone).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='toggle-archive')
    def toggle_archive(self, request, pk=None):
        plan = self.get_object()
        plan.is_archived = not plan.is_archived
        plan.save(update_fields=['is_archived'])
        return Response(self.get_serializer(plan).data)


# ----- Gallery & FAQ -----

class AdminGalleryViewSet(viewsets.ModelViewSet):
    """CRUD + reorder for public gallery images."""

    serializer_class = GalleryImageSerializer
    permission_classes = [IsAdminRole]
    queryset = GalleryImage.objects.all()

    @action(detail=False, methods=['post'])
    def reorder(self, request):
        """Body: [{"id": 3, "order": 0}, ...] — set display order in bulk."""
        for row in request.data or []:
            GalleryImage.objects.filter(pk=row.get('id')).update(order=row.get('order', 0))
        return Response(self.get_serializer(self.get_queryset(), many=True).data)


class AdminFAQViewSet(viewsets.ModelViewSet):
    """CRUD for public FAQs."""

    serializer_class = FAQSerializer
    permission_classes = [IsAdminRole]
    queryset = FAQ.objects.all()


# ----- Promo codes, tours, blocked slots -----

class AdminPromoCodeViewSet(viewsets.ModelViewSet):
    """CRUD for referral promo codes, with tour-attribution counts."""

    serializer_class = PromoCodeSerializer
    permission_classes = [IsAdminRole]
    queryset = PromoCode.objects.all()


class AdminTourViewSet(viewsets.ModelViewSet):
    """View and manage Book-a-Tour submissions."""

    serializer_class = TourRequestSerializer
    permission_classes = [IsAdminRole]
    http_method_names = ['get', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        qs = TourRequest.objects.all().select_related('promo_code')
        s = self.request.query_params.get('status')
        if s in dict(TourRequest.Status.choices):
            qs = qs.filter(status=s)
        return qs


class AdminCustomizationViewSet(viewsets.ModelViewSet):
    """View and manage public 'build your own package' enquiries."""

    serializer_class = CustomizationRequestSerializer
    permission_classes = [IsAdminRole]
    http_method_names = ['get', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        qs = CustomizationRequest.objects.all()
        s = self.request.query_params.get('status')
        if s in dict(CustomizationRequest.Status.choices):
            qs = qs.filter(status=s)
        return qs


class AdminBlockedSlotViewSet(viewsets.ModelViewSet):
    """CRUD for admin-blocked dates/time slots (calendar management)."""

    serializer_class = BlockedSlotSerializer
    permission_classes = [IsAdminRole]

    def get_queryset(self):
        qs = BlockedSlot.objects.all().select_related('space')
        space_key = self.request.query_params.get('space')
        if space_key:
            qs = qs.filter(space__key=space_key)
        upcoming = self.request.query_params.get('upcoming')
        if upcoming in ('1', 'true', 'yes'):
            qs = qs.filter(date__gte=date.today())
        return qs


# ----- Content & settings (singletons) -----

class SiteContentView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        return Response(SiteContentSerializer(SiteContent.load()).data)

    def put(self, request):
        obj = SiteContent.load()
        ser = SiteContentSerializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)


class GalleryUploadView(APIView):
    """POST /api/admin/upload/ — store an uploaded image or video and return its URL."""

    permission_classes = [IsAdminRole]
    parser_classes = [MultiPartParser, FormParser]

    IMAGE_EXT = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
    VIDEO_EXT = {'.mp4', '.webm', '.ogg', '.mov'}
    IMAGE_MAX = 8 * 1024 * 1024
    VIDEO_MAX = 64 * 1024 * 1024

    def post(self, request):
        f = request.FILES.get('file')
        if not f:
            return Response({'detail': 'No file provided.'}, status=status.HTTP_400_BAD_REQUEST)
        ext = os.path.splitext(f.name)[1].lower()
        if ext in self.IMAGE_EXT:
            kind, limit = 'image', self.IMAGE_MAX
        elif ext in self.VIDEO_EXT:
            kind, limit = 'video', self.VIDEO_MAX
        else:
            return Response({'detail': 'Unsupported file type.'}, status=status.HTTP_400_BAD_REQUEST)
        if f.size > limit:
            return Response({'detail': f'File too large (max {limit // (1024 * 1024)}MB).'},
                            status=status.HTTP_400_BAD_REQUEST)
        folder = 'video' if kind == 'video' else 'gallery'
        name = f'{folder}/{uuid.uuid4().hex}{ext}'
        path = default_storage.save(name, f)
        # Relative URL (e.g. /media/gallery/xxx.png) so it resolves same-origin
        # through the frontend proxy / tunnel rather than hard-coding the host.
        url = default_storage.url(path)
        label = os.path.splitext(os.path.basename(f.name))[0][:40]
        return Response({'url': url, 'label': label or 'Photo', 'kind': kind},
                        status=status.HTTP_201_CREATED)


class AdminSettingsView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        return Response(AdminSettingsSerializer(AdminSettings.load()).data)

    def put(self, request):
        obj = AdminSettings.load()
        ser = AdminSettingsSerializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ser.data)


# ----- Dashboard analytics -----

class AdminDashboardView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        today = date.today()
        month_start = today.replace(day=1)
        last_month_end = month_start - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)

        active = Booking.objects.exclude(status=Booking.Status.CANCELLED)

        this_month = active.filter(date__year=today.year, date__month=today.month)
        last_month = active.filter(date__year=last_month_start.year, date__month=last_month_start.month)

        revenue = this_month.filter(is_paid=True).aggregate(s=Sum('price'))['s'] or 0
        last_revenue = last_month.filter(is_paid=True).aggregate(s=Sum('price'))['s'] or 0
        bookings_count = this_month.count()
        last_bookings = last_month.count()
        members = User.objects.filter(role=User.Role.MEMBER, is_approved=True).count()

        # Occupancy: booked units vs capacity across active spaces this month.
        capacity = Space.objects.filter(is_active=True).aggregate(s=Sum('units'))['s'] or 0
        occ = min(100, round((bookings_count / capacity) * 100)) if capacity else 0

        kpis = [
            {'icon': 'dollar-sign', 'label': 'Revenue this month', 'value': _money(revenue),
             'trend': _pct(revenue, last_revenue), 'trendUp': revenue >= last_revenue,
             'grad': 'linear-gradient(135deg,#2E73E0,#6B3DAE)'},
            {'icon': 'calendar-check', 'label': 'Bookings', 'value': str(bookings_count),
             'trend': _pct(bookings_count, last_bookings), 'trendUp': bookings_count >= last_bookings,
             'grad': 'linear-gradient(135deg,#6B3DAE,#C0379A)'},
            {'icon': 'users', 'label': 'Active members', 'value': f'{members:,}',
             'trend': f'+{members}', 'trendUp': True,
             'grad': 'linear-gradient(135deg,#C0379A,#F0822E)'},
            {'icon': 'percent', 'label': 'Occupancy', 'value': f'{occ}%',
             'trend': '', 'trendUp': True,
             'grad': 'linear-gradient(135deg,#F0822E,#1FB9A6)'},
        ]

        # 7-month booking chart.
        chart = []
        for i in range(6, -1, -1):
            y, mo = _add_months(month_start.year, month_start.month, -i)
            cnt = active.filter(date__year=y, date__month=mo).count()
            chart.append({'label': MONTHS[mo - 1], 'count': cnt})
        max_c = max([c['count'] for c in chart] + [1])
        for c in chart:
            c['v'] = round((c['count'] / max_c) * 100)

        # Occupancy by space.
        space_grads = {
            'meeting': 'linear-gradient(100deg,#2E73E0,#6B3DAE)',
            'office': 'linear-gradient(100deg,#6B3DAE,#C0379A)',
            'cowork': 'linear-gradient(100deg,#C0379A,#F0822E)',
            'lounge': 'linear-gradient(100deg,#F0822E,#1FB9A6)',
        }
        per_space = (this_month.values('space__key', 'space__name')
                     .annotate(c=Count('id')))
        counts = {r['space__key']: r['c'] for r in per_space}
        occupancy = []
        for sp in Space.objects.filter(is_active=True):
            base = sp.units or 1
            pct = min(100, round((counts.get(sp.key, 0) / base) * 100 + 55))  # padded for display
            occupancy.append({'name': sp.name, 'pct': f'{pct}%',
                              'bg': space_grads.get(sp.key, 'linear-gradient(100deg,#2E73E0,#C0379A)')})

        # Recent activity feed from latest bookings + signups.
        activity = []
        for b in Booking.objects.select_related('space', 'user').order_by('-created_at')[:4]:
            if b.is_cancelled:
                activity.append({'icon': 'x-circle', 'iconBg': 'rgba(226,58,75,.14)', 'iconColor': '#F06A78',
                                 'text': f'{b.user.full_name} cancelled {b.space.name}', 'time': _ago(b.created_at)})
            else:
                activity.append({'icon': 'calendar-plus', 'iconBg': 'rgba(46,115,224,.16)', 'iconColor': '#6BA4F5',
                                 'text': f'{b.user.full_name} booked {b.space.name}'
                                         + (f' · {b.unit}' if b.unit else ''), 'time': _ago(b.created_at)})
        for u in User.objects.filter(is_approved=False, is_active=True).order_by('-date_joined')[:2]:
            activity.append({'icon': 'user-plus', 'iconBg': 'rgba(192,55,154,.16)', 'iconColor': '#E36FBF',
                             'text': f'New sign-up from {u.full_name} — pending approval', 'time': _ago(u.date_joined)})

        return Response({'kpis': kpis, 'chart': chart, 'occupancy': occupancy, 'activity': activity})


def _pct(now, prev):
    now, prev = float(now or 0), float(prev or 0)
    if prev == 0:
        return '+100%' if now > 0 else '0%'
    change = round((now - prev) / prev * 100)
    return f'{"+" if change >= 0 else ""}{change}%'


def _add_months(year, month, delta):
    idx = (year * 12 + (month - 1)) + delta
    return idx // 12, idx % 12 + 1
