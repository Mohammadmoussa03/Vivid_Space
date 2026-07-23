import uuid

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models


def normalize_email(value):
    """Canonical form of an email address: trimmed and lowercased.

    Email is the login credential here, so it must round-trip through the DB
    case-insensitively — otherwise "John@X.com" and "john@x.com" are two
    different accounts to Postgres. Every write path funnels through this.
    """
    return (value or '').strip().lower()


class UserManager(BaseUserManager):
    """Manager for the email-based custom user model."""

    use_in_migrations = True

    def get_by_natural_key(self, username):
        """Case-insensitive credential lookup (used by Django's auth backend)."""
        return self.get(**{f'{self.model.USERNAME_FIELD}__iexact': normalize_email(username)})

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError('An email address is required.')
        email = normalize_email(self.normalize_email(email))
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('role', User.Role.MEMBER)
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('role', User.Role.ADMIN)
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_approved', True)
        extra_fields.setdefault('email_verified', True)
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Vivid Space member / admin account, identified by email."""

    class Role(models.TextChoices):
        MEMBER = 'member', 'Member'
        ADMIN = 'admin', 'Admin'

    # Stable, non-sequential public identifier — safe to expose in URLs/APIs
    # without leaking user counts or enabling ID enumeration.
    uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)

    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=80, blank=True)
    last_name = models.CharField(max_length=80, blank=True)
    company = models.CharField(max_length=160, blank=True)

    role = models.CharField(max_length=10, choices=Role.choices, default=Role.MEMBER)

    # New signups stay pending until an admin approves them.
    is_approved = models.BooleanField(default=False)

    # Proof the address is real: set when the member clicks the link emailed at
    # signup. Login is refused until it's True (admins are exempt).
    email_verified = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    date_joined = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        ordering = ['-date_joined']

    def save(self, *args, **kwargs):
        # Last line of defence: whatever the write path (API, django-admin,
        # shell, management command), the stored address is canonical.
        self.email = normalize_email(self.email)
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.email

    @property
    def full_name(self):
        name = f'{self.first_name} {self.last_name}'.strip()
        return name or self.email

    @property
    def is_admin(self):
        return self.role == self.Role.ADMIN


class SocialAccount(models.Model):
    """A third-party identity (Google, Apple, …) linked to a local account.

    Kept in its own table rather than as a flag on User so one member can link
    several providers, and so the provider's stable subject id is what we match
    returning users on — an address can change, `sub` can't.
    """

    class Provider(models.TextChoices):
        GOOGLE = 'google', 'Google'
        APPLE = 'apple', 'Apple'

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='social_accounts')
    provider = models.CharField(max_length=20, choices=Provider.choices)
    # The provider's `sub` claim: stable for the life of the account.
    provider_uid = models.CharField(max_length=255)
    # The address the provider asserted at link time — kept for support/debugging
    # only; `user.email` remains the credential of record.
    provider_email = models.EmailField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_login_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['provider', 'provider_uid'],
                                    name='unique_social_identity'),
        ]
        ordering = ['provider']

    def __str__(self):
        return f'{self.get_provider_display()} → {self.user.email}'
