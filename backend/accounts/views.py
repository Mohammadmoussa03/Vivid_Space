from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import IntegrityError
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.middleware.csrf import get_token
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from django.db import transaction
from django.utils import timezone

from .cookies import clear_auth_cookies, set_auth_cookies
from .models import SocialAccount, normalize_email
from .social import PROVIDERS, SocialAuthError, extract_identity, verify_id_token
from .emails import (
    send_email_already_registered,
    send_email_verification,
    send_password_reset,
)
from .throttling import LoginAccountThrottle, LoginIPThrottle
from .tokens import blacklist_user_tokens, email_verification_token
from .serializers import (
    LoginSerializer,
    PasswordResetSerializer,
    ProfileUpdateSerializer,
    RegisterSerializer,
    ResendVerificationSerializer,
    UserSerializer,
)

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    """POST /api/auth/register/ — create an account awaiting email confirmation."""

    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    throttle_scope = 'register'

    # Identical response whether or not the email is already registered, so the
    # endpoint can't be used to enumerate accounts. The generic message avoids
    # confirming existence; the response never echoes the user back.
    GENERIC_RESPONSE = {
        'detail': 'Thanks — check your inbox for a link to confirm your email '
                  'address and activate your account.',
    }

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']

        # Address already taken: don't create a duplicate and don't reveal it —
        # instead quietly notify the real owner out of band.
        if User.objects.filter(email__iexact=email).exists():
            send_email_already_registered(email)
            return Response(self.GENERIC_RESPONSE, status=status.HTTP_201_CREATED)

        try:
            user = serializer.save()
        except IntegrityError:
            # Lost a race with a concurrent signup for the same email — same
            # generic response, still no enumeration signal.
            send_email_already_registered(email)
            return Response(self.GENERIC_RESPONSE, status=status.HTTP_201_CREATED)
        # The account exists but can't log in until this link is clicked.
        send_email_verification(user)
        return Response(self.GENERIC_RESPONSE, status=status.HTTP_201_CREATED)


class LoginView(TokenObtainPairView):
    """POST /api/auth/login/ — sets httpOnly JWT cookies, returns {user, csrftoken}.

    The tokens are delivered only as httpOnly cookies; they never appear in the
    JSON body, so nothing token-shaped is visible in the browser console/network.
    """

    serializer_class = LoginSerializer
    permission_classes = [permissions.AllowAny]
    # Per-IP throttle (fast brute force) + per-account throttle (distributed
    # brute force / account lockout).
    throttle_classes = [LoginIPThrottle, LoginAccountThrottle]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as exc:
            raise InvalidToken(exc.args[0])
        data = serializer.validated_data
        response = Response(
            {'user': data['user'], 'csrftoken': get_token(request)},
            status=status.HTTP_200_OK,
        )
        set_auth_cookies(response, access=data['access'], refresh=data['refresh'])
        return response


class SocialLoginView(APIView):
    """Exchange a provider ID token for this app's own session cookies.

    The provider only ever proves *identity*; the session itself is the same
    httpOnly-cookie JWT pair every other login issues, so nothing downstream
    (CSRF, rotation, blacklist) needs to know social sign-in exists.

    Subclass and set `provider_key` to add a provider.
    """

    provider_key = None
    permission_classes = [permissions.AllowAny]
    throttle_scope = 'social_auth'

    def post(self, request):
        provider = PROVIDERS[self.provider_key]
        client_id = getattr(settings, provider.client_id_setting, '')
        # `credential` is what Google Identity Services calls it; `id_token` is
        # the generic name and what Apple's JS returns.
        token = request.data.get('credential') or request.data.get('id_token') or ''

        try:
            claims = verify_id_token(provider, token, client_id)
            identity = extract_identity(provider, claims)
        except SocialAuthError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        user, created = self._resolve_user(provider, identity)

        if not user.is_active:
            return Response({'detail': 'This account has been deactivated.'},
                            status=status.HTTP_403_FORBIDDEN)
        if not user.is_approved and not user.is_admin:
            return Response(
                {'detail': 'Your account is pending approval. We\'ll email you once it\'s active.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        refresh = RefreshToken.for_user(user)
        response = Response(
            {'user': UserSerializer(user).data,
             'csrftoken': get_token(request),
             'created': created},
            status=status.HTTP_200_OK,
        )
        set_auth_cookies(response, access=str(refresh.access_token), refresh=str(refresh))
        return response

    @transaction.atomic
    def _resolve_user(self, provider, identity):
        """Find, link, or create the local account behind a verified identity.

        Returns (user, created). Three cases, in order of trust:
        1. We've seen this provider subject before — the linked user, whatever
           their address is now.
        2. A local account already owns the (provider-verified) address — link
           the identity to it rather than forking a second account.
        3. Nobody owns it — create a member, already email-verified.
        """
        email = normalize_email(identity['email'])
        link = (SocialAccount.objects
                .select_related('user')
                .filter(provider=provider.key, provider_uid=identity['uid'])
                .first())
        if link:
            link.last_login_at = timezone.now()
            link.provider_email = email
            link.save(update_fields=['last_login_at', 'provider_email'])
            return link.user, False

        user = User.objects.filter(email__iexact=email).first()
        created = False
        if user is None:
            # No password is set, so the password login path stays closed for
            # this account until the member sets one via "Forgot password".
            user = User.objects.create_user(
                email=email,
                password=None,
                first_name=identity['first_name'],
                last_name=identity['last_name'],
                is_approved=True,
                email_verified=True,   # the provider vouched for the address
                role=User.Role.MEMBER,
            )
            created = True
        elif not user.email_verified:
            # A verified provider address settles the question for an account
            # that signed up but never clicked the confirmation link.
            user.email_verified = True
            user.save(update_fields=['email_verified'])

        SocialAccount.objects.create(
            user=user, provider=provider.key, provider_uid=identity['uid'],
            provider_email=email, last_login_at=timezone.now(),
        )
        return user, created


class GoogleLoginView(SocialLoginView):
    """POST /api/auth/social/google/ — body: {"credential": "<GIS ID token>"}."""

    provider_key = 'google'


class CookieTokenRefreshView(APIView):
    """POST /api/auth/token/refresh/ — rotate tokens using the refresh cookie.

    Reads the refresh token from its httpOnly cookie (no request body), rotates
    it (the consumed refresh token is blacklisted), and writes fresh cookies.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        raw_refresh = request.COOKIES.get(settings.AUTH_COOKIE_REFRESH)
        if not raw_refresh:
            return Response({'detail': 'No refresh token.'},
                            status=status.HTTP_401_UNAUTHORIZED)
        serializer = TokenRefreshSerializer(data={'refresh': raw_refresh})
        try:
            serializer.is_valid(raise_exception=True)
        except (TokenError, InvalidToken):
            # Expired / blacklisted / tampered — drop the stale cookies.
            response = Response({'detail': 'Token is invalid or expired.'},
                                status=status.HTTP_401_UNAUTHORIZED)
            clear_auth_cookies(response)
            return response
        data = serializer.validated_data
        response = Response(status=status.HTTP_200_OK)
        # Rotation is on, so both a new access and new refresh come back.
        set_auth_cookies(response, access=data.get('access'), refresh=data.get('refresh'))
        return response


class LogoutView(APIView):
    """POST /api/auth/logout/ — blacklist the refresh token and clear cookies."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        raw_refresh = request.COOKIES.get(settings.AUTH_COOKIE_REFRESH)
        if raw_refresh:
            try:
                RefreshToken(raw_refresh).blacklist()
            except TokenError:
                pass  # already expired/blacklisted — nothing to revoke
        response = Response(status=status.HTTP_205_RESET_CONTENT)
        clear_auth_cookies(response)
        return response


class CsrfView(APIView):
    """GET /api/auth/csrf/ — ensure the SPA has a csrftoken cookie to echo back."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return Response({'csrftoken': get_token(request)})


class PasswordResetView(APIView):
    """POST /api/auth/password-reset/ — emails a reset link.

    Always returns 200 (even for unknown emails) to avoid account enumeration.
    """

    permission_classes = [permissions.AllowAny]
    throttle_scope = 'password_reset'

    def post(self, request):
        serializer = PasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if user:
            send_password_reset(user)
        return Response(
            {'detail': 'If an account exists for that email, a reset link is on its way.'},
            status=status.HTTP_200_OK,
        )


class PasswordResetConfirmView(APIView):
    """POST /api/auth/password-reset/confirm/ — set a new password from a token.

    Body: {"uid": "...", "token": "...", "password": "..."} from the emailed link.
    """

    permission_classes = [permissions.AllowAny]
    throttle_scope = 'password_reset'

    def post(self, request):
        uid = request.data.get('uid') or ''
        token = request.data.get('token') or ''
        password = request.data.get('password') or ''
        try:
            user = User.objects.get(pk=force_str(urlsafe_base64_decode(uid)))
        except (User.DoesNotExist, ValueError, TypeError, OverflowError):
            user = None
        if not user or not default_token_generator.check_token(user, token):
            return Response({'detail': 'This reset link is invalid or has expired.'},
                            status=status.HTTP_400_BAD_REQUEST)
        try:
            validate_password(password, user)
        except DjangoValidationError as exc:
            return Response({'password': list(exc.messages)},
                            status=status.HTTP_400_BAD_REQUEST)
        user.set_password(password)
        user.save(update_fields=['password'])
        # Revoke any sessions that were live before the reset (stolen tokens
        # must not survive a password reset).
        blacklist_user_tokens(user)
        return Response({'detail': 'Your password has been reset. You can now log in.'},
                        status=status.HTTP_200_OK)


class VerifyEmailView(APIView):
    """POST /api/auth/verify-email/ — confirm an address from the emailed link.

    Body: {"uid": "...", "token": "..."} as carried by the link's query string.
    """

    permission_classes = [permissions.AllowAny]
    throttle_scope = 'verify_email'

    def post(self, request):
        uid = request.data.get('uid') or ''
        token = request.data.get('token') or ''
        try:
            user = User.objects.get(pk=force_str(urlsafe_base64_decode(uid)))
        except (User.DoesNotExist, ValueError, TypeError, OverflowError):
            user = None
        if user and user.email_verified:
            # The link is single-use (email_verified is in the token hash), so a
            # second click can't re-validate — treat it as success, not an error.
            return Response({'detail': 'Your email is already confirmed. You can log in.'},
                            status=status.HTTP_200_OK)
        if not user or not email_verification_token.check_token(user, token):
            return Response({'detail': 'This confirmation link is invalid or has expired.'},
                            status=status.HTTP_400_BAD_REQUEST)
        user.email_verified = True
        user.save(update_fields=['email_verified'])
        return Response({'detail': 'Email confirmed — you can now log in.'},
                        status=status.HTTP_200_OK)


class ResendVerificationView(APIView):
    """POST /api/auth/resend-verification/ — send the confirmation link again.

    Always returns 200, and stays silent for unknown or already-verified
    addresses, so it can't be used to enumerate accounts.
    """

    permission_classes = [permissions.AllowAny]
    throttle_scope = 'verify_email'

    def post(self, request):
        serializer = ResendVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.filter(email__iexact=serializer.validated_data['email'],
                                   is_active=True, email_verified=False).first()
        if user:
            send_email_verification(user)
        return Response(
            {'detail': 'If that account still needs confirming, a new link is on its way.'},
            status=status.HTTP_200_OK,
        )


class MeView(generics.RetrieveUpdateAPIView):
    """GET/PATCH /api/auth/me/ — current user's profile."""

    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

    def get_serializer_class(self):
        if self.request.method in ('PUT', 'PATCH'):
            return ProfileUpdateSerializer
        return UserSerializer

    def update(self, request, *args, **kwargs):
        old_email = self.get_object().email
        super().update(request, *args, **kwargs)
        user = self.get_object()
        response = Response(UserSerializer(user).data)
        # Email is the login credential — changing it revokes existing tokens
        # (project's "revoke on credential change" rule) and re-issues fresh
        # cookies so the member stays signed in with new tokens.
        if user.email != old_email:
            blacklist_user_tokens(user)
            refresh = RefreshToken.for_user(user)
            set_auth_cookies(response, access=str(refresh.access_token), refresh=str(refresh))
        return response
