"""Helpers for setting/clearing the httpOnly JWT cookies consistently.

Centralised so login, refresh and logout all use identical flags (Secure,
SameSite, domain, path) — a mismatch would leave stale cookies the browser
refuses to overwrite or delete.
"""
from django.conf import settings


def _flags():
    return {
        'secure': settings.AUTH_COOKIE_SECURE,
        'samesite': settings.AUTH_COOKIE_SAMESITE,
        'domain': settings.AUTH_COOKIE_DOMAIN,
        'path': '/',
    }


def _seconds(key):
    return int(settings.SIMPLE_JWT[key].total_seconds())


def set_auth_cookies(response, access=None, refresh=None):
    """Attach the access and/or refresh token as httpOnly cookies."""
    if access is not None:
        response.set_cookie(
            settings.AUTH_COOKIE_ACCESS, access,
            max_age=_seconds('ACCESS_TOKEN_LIFETIME'), httponly=True, **_flags(),
        )
    if refresh is not None:
        response.set_cookie(
            settings.AUTH_COOKIE_REFRESH, refresh,
            max_age=_seconds('REFRESH_TOKEN_LIFETIME'), httponly=True, **_flags(),
        )
    return response


def clear_auth_cookies(response):
    """Remove both auth cookies (used on logout)."""
    for name in (settings.AUTH_COOKIE_ACCESS, settings.AUTH_COOKIE_REFRESH):
        response.delete_cookie(
            name,
            path='/',
            domain=settings.AUTH_COOKIE_DOMAIN,
            samesite=settings.AUTH_COOKIE_SAMESITE,
        )
    return response
