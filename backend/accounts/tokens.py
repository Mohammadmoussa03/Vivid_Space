"""Token revocation helpers.

JWTs are stateless, so a password change doesn't invalidate tokens already in
the wild. After any credential change we blacklist the user's outstanding
refresh tokens so an attacker holding a stolen session is kicked out.
"""
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)


def blacklist_user_tokens(user):
    """Blacklist every outstanding refresh token for a user (best-effort)."""
    for token in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=token)
