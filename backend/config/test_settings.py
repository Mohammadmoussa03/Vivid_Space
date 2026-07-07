"""Test settings: run the suite on an in-memory SQLite database.

Lets `manage.py test --settings=config.test_settings` run without needing the
PostgreSQL role to hold the CREATEDB privilege. Production/dev keep using
PostgreSQL via the default config.settings.
"""
from .settings import *  # noqa: F401,F403

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# Keep tour-notification emails out of the console during tests.
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

# Effectively disable rate limiting in tests: throttle state persists in the
# process cache across test methods and would otherwise cause flaky,
# order-dependent 429s. Rates are kept defined (the login view's explicit
# throttles require them) but set high enough never to trip.
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    'DEFAULT_THROTTLE_CLASSES': (),
    'DEFAULT_THROTTLE_RATES': {
        k: '100000/min' for k in
        ('anon', 'user', 'login', 'login_account', 'register', 'password_reset')
    },
}
