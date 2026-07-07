"""Cookie-based JWT authentication.

The access token is transported in an **httpOnly** cookie (`vs_access`) rather
than an `Authorization` header, so it is never readable from JavaScript / the
browser console and can't be exfiltrated by XSS. Because the browser now sends
that cookie automatically on every request, we re-introduce CSRF protection on
unsafe methods (double-submit token), mirroring DRF's SessionAuthentication.
"""
from django.conf import settings
from django.middleware.csrf import CsrfViewMiddleware
from rest_framework import exceptions
from rest_framework_simplejwt.authentication import JWTAuthentication


class _CSRFCheck(CsrfViewMiddleware):
    def _reject(self, request, reason):
        # Return the failure reason instead of raising/returning an HttpResponse.
        return reason


class CookieJWTAuthentication(JWTAuthentication):
    """Validate the JWT carried in the `AUTH_COOKIE_ACCESS` cookie."""

    def authenticate(self, request):
        raw_token = request.COOKIES.get(settings.AUTH_COOKIE_ACCESS)
        if not raw_token:
            # No cookie → unauthenticated (lets AllowAny endpoints work).
            return None

        validated_token = self.get_validated_token(raw_token)
        # Only enforce CSRF once we know the request is riding on our auth cookie.
        self.enforce_csrf(request)
        return self.get_user(validated_token), validated_token

    def enforce_csrf(self, request):
        """Reject unsafe methods lacking a valid CSRF token.

        Django's CsrfViewMiddleware already treats GET/HEAD/OPTIONS/TRACE as
        safe, so this is effectively a no-op for reads.
        """
        def dummy_get_response(_request):  # pragma: no cover - never called
            return None

        check = _CSRFCheck(dummy_get_response)
        check.process_request(request)
        reason = check.process_view(request, None, (), {})
        if reason:
            raise exceptions.PermissionDenied(f'CSRF Failed: {reason}')
