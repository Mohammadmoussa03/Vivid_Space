"""Transactional emails for the account lifecycle (signup, approval, password).

Every send is best-effort: a mail failure must never break the request that
triggered it, so all sends are wrapped and use fail_silently.
"""
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


def owner_recipient():
    """Where owner/admin notifications go: Admin → Settings, else OWNER_EMAIL."""
    # Imported lazily to avoid an import cycle at app-load time.
    from bookings.models import AdminSettings
    return (AdminSettings.load().notification_email
            or getattr(settings, 'OWNER_EMAIL', '') or settings.DEFAULT_FROM_EMAIL)


def _send(subject, body, recipient):
    if not recipient:
        return
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL,
                  [recipient] if isinstance(recipient, str) else list(recipient),
                  fail_silently=True)
    except Exception:
        pass


def send_signup_received(user):
    """Confirm to a new member that their signup is in and pending approval."""
    if not user.email:
        return
    body = (
        f'Hi {user.full_name or "there"},\n\n'
        f'Thanks for signing up to Vivid Space. Your account has been created and '
        f'is now waiting for a quick review by our team.\n\n'
        f'We\'ll email you as soon as it\'s approved — then you can log in and start '
        f'booking spaces.\n\n'
        f'— The Vivid Space team\n'
    )
    _send('Welcome to Vivid Space — your account is pending approval', body, user.email)


def notify_owner_new_signup(user):
    """Tell the owner/admin a new member is waiting for approval."""
    body = (
        f'A new member signed up and is awaiting approval.\n\n'
        f'Name:    {user.full_name or "—"}\n'
        f'Email:   {user.email}\n'
        f'Company: {user.company or "—"}\n\n'
        f'Approve or reject them in the admin panel → Users.\n'
    )
    _send(f'New signup pending approval — {user.full_name or user.email}',
          body, owner_recipient())


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
