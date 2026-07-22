"""Token revocation helpers and the email-verification token generator.

JWTs are stateless, so a password change doesn't invalidate tokens already in
the wild. After any credential change we blacklist the user's outstanding
refresh tokens so an attacker holding a stolen session is kicked out.
"""
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from rest_framework_simplejwt.token_blacklist.models import (
    BlacklistedToken,
    OutstandingToken,
)


class EmailVerificationTokenGenerator(PasswordResetTokenGenerator):
    """Signed, expiring token for the "confirm your email" link.

    A distinct `key_salt` from Django's password-reset generator keeps the two
    link types from being interchangeable — a verification link must never be
    usable to set a password, or vice versa. `email_verified` is part of the
    hash so a link stops working the moment it's been used once.
    """

    key_salt = 'accounts.EmailVerificationTokenGenerator'

    def _make_hash_value(self, user, timestamp):
        return f'{user.pk}{user.email}{user.email_verified}{timestamp}'


email_verification_token = EmailVerificationTokenGenerator()


def blacklist_user_tokens(user):
    """Blacklist every outstanding refresh token for a user (best-effort)."""
    for token in OutstandingToken.objects.filter(user=user):
        BlacklistedToken.objects.get_or_create(token=token)
