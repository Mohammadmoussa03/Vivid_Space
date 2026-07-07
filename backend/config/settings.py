"""
Django settings for the Vivid Space backend.

Configured for Django REST Framework + SimpleJWT (Bearer auth) against the
existing Vite/React frontend, backed by PostgreSQL. Secrets and the DB
connection are read from a local .env file (see .env.example).
"""

from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv
import os

BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from backend/.env if present.
load_dotenv(BASE_DIR / '.env')


def env(key, default=None):
    val = os.environ.get(key, default)
    return val


def env_bool(key, default=False):
    val = os.environ.get(key)
    if val is None:
        return default
    return val.strip().lower() in ('1', 'true', 'yes', 'on')


def env_list(key, default=''):
    raw = os.environ.get(key, default)
    return [item.strip() for item in raw.split(',') if item.strip()]


_INSECURE_SECRET = 'django-insecure-dev-only-change-me'
SECRET_KEY = env('DJANGO_SECRET_KEY', _INSECURE_SECRET)

DEBUG = env_bool('DJANGO_DEBUG', False)

ALLOWED_HOSTS = env_list('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1')

# Fail fast in production rather than silently running with the throwaway dev key.
if not DEBUG and SECRET_KEY == _INSECURE_SECRET:
    raise RuntimeError(
        'DJANGO_SECRET_KEY must be set to a strong, unique value when DEBUG is off.'
    )


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party
    'rest_framework',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',

    # Local apps
    'accounts',
    'bookings',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'config.middleware.ContentSecurityPolicyMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Database (PostgreSQL)

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env('POSTGRES_DB', 'vivid_space'),
        'USER': env('POSTGRES_USER', 'vivid'),
        'PASSWORD': env('POSTGRES_PASSWORD', ''),
        'HOST': env('POSTGRES_HOST', 'localhost'),
        'PORT': env('POSTGRES_PORT', '5432'),
    }
}


# Custom user model (email-based login).
AUTH_USER_MODEL = 'accounts.User'


AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


# Static files
STATIC_URL = 'static/'
# collectstatic target (Django admin assets etc.). Served by nginx in production;
# harmless in dev. Overridable via env for hosts that need a different path.
STATIC_ROOT = env('DJANGO_STATIC_ROOT', str(BASE_DIR / 'staticfiles'))

# Uploaded media (gallery images).
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# S3 media storage (production). Enabled only when AWS_STORAGE_BUCKET_NAME is set,
# so local dev keeps using the filesystem (MEDIA_ROOT) above with no extra config.
# Credentials come from the EC2 instance's IAM role (preferred) or the standard
# AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY env vars — boto3 resolves them itself.
AWS_STORAGE_BUCKET_NAME = env('AWS_STORAGE_BUCKET_NAME', '')
if AWS_STORAGE_BUCKET_NAME:
    AWS_S3_REGION_NAME = env('AWS_S3_REGION_NAME', '')
    # Optional CloudFront domain in front of the bucket; else the raw S3 host.
    AWS_S3_CUSTOM_DOMAIN = env('AWS_S3_CUSTOM_DOMAIN', '')
    AWS_QUERYSTRING_AUTH = env_bool('AWS_QUERYSTRING_AUTH', False)  # public objects → clean, stable URLs
    AWS_S3_FILE_OVERWRITE = False   # don't clobber same-named uploads
    AWS_DEFAULT_ACL = None          # rely on the bucket policy, not per-object ACLs
    STORAGES = {
        'default': {'BACKEND': 'storages.backends.s3boto3.S3Boto3Storage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    }
    MEDIA_URL = (
        f'https://{AWS_S3_CUSTOM_DOMAIN}/' if AWS_S3_CUSTOM_DOMAIN
        else f'https://{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com/'
    )

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# Django REST Framework + SimpleJWT

REST_FRAMEWORK = {
    # Tokens are carried in httpOnly cookies (see accounts/authentication.py),
    # never in JS-readable storage, and CSRF is enforced on unsafe methods.
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'accounts.authentication.CookieJWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
    ),
    # Rate limiting — blunts credential stuffing / brute force / abuse.
    'DEFAULT_THROTTLE_CLASSES': (
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
        'rest_framework.throttling.ScopedRateThrottle',
    ),
    'DEFAULT_THROTTLE_RATES': {
        'anon': env('THROTTLE_ANON', '60/min'),
        'user': env('THROTTLE_USER', '240/min'),
        'login': env('THROTTLE_LOGIN', '10/min'),               # per IP
        'login_account': env('THROTTLE_LOGIN_ACCOUNT', '20/hour'),  # per account (lockout)
        'register': env('THROTTLE_REGISTER', '5/min'),
        'password_reset': env('THROTTLE_PASSWORD_RESET', '5/min'),
    },
}

SIMPLE_JWT = {
    # Short access lifetime limits the window a leaked/post-logout access token
    # stays usable (logout can only blacklist the refresh token, not the JWT).
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    # Rotate on every refresh and blacklist the consumed refresh token so a
    # captured/old refresh token can't be replayed.
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}

# httpOnly-cookie transport for the JWT pair. Secure is on whenever DEBUG is off
# (i.e. anywhere served over HTTPS); SameSite=Lax is safe for our single-origin
# setup and still allows top-level navigations.
AUTH_COOKIE_ACCESS = 'vs_access'
AUTH_COOKIE_REFRESH = 'vs_refresh'
AUTH_COOKIE_SECURE = env_bool('AUTH_COOKIE_SECURE', not DEBUG)
AUTH_COOKIE_SAMESITE = env('AUTH_COOKIE_SAMESITE', 'Lax')
AUTH_COOKIE_DOMAIN = env('AUTH_COOKIE_DOMAIN', None) or None


# CORS — allow the Vite dev server / configured origins to talk to the API.
CORS_ALLOWED_ORIGINS = env_list(
    'CORS_ALLOWED_ORIGINS',
    'http://localhost:5173,http://127.0.0.1:5173',
)
CORS_ALLOW_CREDENTIALS = True


# CSRF — cookies are now sent automatically, so unsafe methods require a CSRF
# token (double-submit). The SPA reads the non-httpOnly csrftoken cookie and
# echoes it back in the X-CSRFToken header (see frontend/src/lib/api.js).
CSRF_TRUSTED_ORIGINS = env_list(
    'CSRF_TRUSTED_ORIGINS',
    'http://localhost:5173,http://127.0.0.1:5173',
)
CSRF_COOKIE_HTTPONLY = False  # the SPA must read it to echo it back
CSRF_COOKIE_SAMESITE = AUTH_COOKIE_SAMESITE
CSRF_COOKIE_SECURE = not DEBUG


# ---------------------------------------------------------------------------
# Security headers / cookie flags. The transport-security bits are gated on
# `not DEBUG` so plain-http local development keeps working.
# ---------------------------------------------------------------------------
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = AUTH_COOKIE_SAMESITE
SESSION_COOKIE_SECURE = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'

if not DEBUG:
    SECURE_SSL_REDIRECT = env_bool('SECURE_SSL_REDIRECT', True)
    # Trust the X-Forwarded-Proto header set by the reverse proxy / ngrok.
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_HSTS_SECONDS = int(env('SECURE_HSTS_SECONDS', '31536000'))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True


# Cache — used by DRF throttling (rate limits / login lockout). LocMem is
# per-process, so a multi-worker production deployment needs a SHARED cache for
# throttles to be enforced globally: set REDIS_URL and we switch automatically.
_REDIS_URL = env('REDIS_URL')
if _REDIS_URL:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': _REDIS_URL,
        }
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'vivid-space-locmem',
        }
    }


# Content-Security-Policy header emitted by ContentSecurityPolicyMiddleware.
# The SPA is served separately (Vite/static host); this primarily hardens
# Django-served responses (API errors, /django-admin). Override per-env if a
# production static host should send its own stricter policy for the SPA HTML.
CONTENT_SECURITY_POLICY = env(
    'CONTENT_SECURITY_POLICY',
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: https:; "
    "media-src 'self' https:; "
    "font-src 'self' data:; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'",
)


# Email — defaults to the console backend (emails print to the runserver console).
# As soon as EMAIL_HOST_USER is set in .env we switch to real SMTP delivery
# automatically; set EMAIL_BACKEND explicitly to override either way.
EMAIL_HOST = env('EMAIL_HOST', 'localhost')
EMAIL_PORT = int(env('EMAIL_PORT', '587'))
EMAIL_HOST_USER = env('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = env_bool('EMAIL_USE_TLS', True)
EMAIL_USE_SSL = env_bool('EMAIL_USE_SSL', False)
EMAIL_TIMEOUT = int(env('EMAIL_TIMEOUT', '15'))
_default_email_backend = (
    'django.core.mail.backends.smtp.EmailBackend' if EMAIL_HOST_USER
    else 'django.core.mail.backends.console.EmailBackend'
)
EMAIL_BACKEND = env('EMAIL_BACKEND', _default_email_backend)
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', 'Vivid Space <no-reply@vividspace.co>')
SERVER_EMAIL = DEFAULT_FROM_EMAIL
# Where owner/admin notifications go when AdminSettings.notification_email is blank.
OWNER_EMAIL = env('OWNER_EMAIL', 'owner@vividspace.co')
# Public site origin, used to build links (e.g. password-reset) inside emails.
FRONTEND_URL = env('FRONTEND_URL', 'http://localhost:5173').rstrip('/')
