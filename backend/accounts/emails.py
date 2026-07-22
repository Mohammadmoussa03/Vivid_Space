"""Transactional emails for the account lifecycle (signup, approval, password).

Every send is best-effort: a mail failure must never break the request that
triggered it, so all sends are wrapped and use fail_silently.
"""
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .tokens import email_verification_token


def _send(subject, body, recipient):
    if not recipient:
        return
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL,
                  [recipient] if isinstance(recipient, str) else list(recipient),
                  fail_silently=True)
    except Exception:
        pass


def build_verify_url(user):
    """A one-time email-confirmation link pointing at the frontend."""
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = email_verification_token.make_token(user)
    return f'{settings.FRONTEND_URL}/?verify_uid={uid}&verify_token={token}'


def send_email_verification(user):
    """Email a new member the link that unlocks their account."""
    if not user.email:
        return
    body = (
        f'Hi {user.full_name or "there"},\n\n'
        f'Thanks for signing up to Vivid Space. Confirm this email address to '
        f'activate your account:\n\n'
        f'{build_verify_url(user)}\n\n'
        f'Once confirmed you can log in and start booking spaces. If you didn\'t '
        f'sign up, you can safely ignore this email.\n\n'
        f'— The Vivid Space team\n'
    )
    _send('Confirm your email — Vivid Space', body, user.email)


def send_email_already_registered(email):
    """Sent when someone tries to sign up with an email that's already in use.

    Lets us return an identical (non-enumerating) API response for new and
    existing emails, while still giving the real account owner a useful heads-up.
    """
    if not email:
        return
    body = (
        f'Hi,\n\n'
        f'Someone just tried to create a Vivid Space account with this email '
        f'address, but it\'s already registered.\n\n'
        f'If this was you, there\'s nothing to do — just log in. If you\'ve '
        f'forgotten your password, use the "Forgot password" link:\n'
        f'{settings.FRONTEND_URL}/\n\n'
        f'If it wasn\'t you, you can safely ignore this email.\n\n'
        f'— The Vivid Space team\n'
    )
    _send('About your Vivid Space account', body, email)


def send_account_approved(user):
    """Tell a member their account is approved and they can log in."""
    if not user.email:
        return
    body = (
        f'Hi {user.full_name or "there"},\n\n'
        f'Good news — your Vivid Space account has been approved. '
        f'You can now log in and book spaces:\n\n'
        f'{settings.FRONTEND_URL}/\n\n'
        f'Welcome aboard!\n\n'
        f'— The Vivid Space team\n'
    )
    _send('Your Vivid Space account is approved', body, user.email)


def send_password_set_by_admin(user, password):
    """Email a member the new password an admin set for them."""
    if not user.email:
        return
    body = (
        f'Hi {user.full_name or "there"},\n\n'
        f'An administrator has set a new password for your Vivid Space account.\n\n'
        f'Email:    {user.email}\n'
        f'Password: {password}\n\n'
        f'Please log in and change it from your profile:\n{settings.FRONTEND_URL}/\n\n'
        f'— The Vivid Space team\n'
    )
    _send('Your Vivid Space password was reset', body, user.email)


def build_reset_url(user):
    """A one-time password-reset link pointing at the frontend."""
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    return f'{settings.FRONTEND_URL}/?reset_uid={uid}&reset_token={token}', uid, token


def send_password_reset(user):
    """Email a member a secure password-reset link."""
    if not user.email:
        return
    reset_url, _uid, _token = build_reset_url(user)
    body = (
        f'Hi {user.full_name or "there"},\n\n'
        f'We received a request to reset your Vivid Space password. '
        f'Click the link below to choose a new one:\n\n'
        f'{reset_url}\n\n'
        f'If you didn\'t request this, you can safely ignore this email — '
        f'your password won\'t change.\n\n'
        f'— The Vivid Space team\n'
    )
    _send('Reset your Vivid Space password', body, user.email)
