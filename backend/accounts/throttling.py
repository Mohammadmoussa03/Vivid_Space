"""Login throttles.

Two independent limits guard the login endpoint:
- `LoginIPThrottle` — caps attempts from a single IP (fast brute-force).
- `LoginAccountThrottle` — caps attempts against a single account regardless of
  source IP (distributed / rotating-proxy brute force). This is the account
  lockout the plain IP throttle can't provide.
"""
from rest_framework.throttling import SimpleRateThrottle


class LoginIPThrottle(SimpleRateThrottle):
    scope = 'login'

    def get_cache_key(self, request, view):
        if request.method != 'POST':
            return None
        return self.cache_format % {'scope': self.scope, 'ident': self.get_ident(request)}


class LoginAccountThrottle(SimpleRateThrottle):
    scope = 'login_account'

    def get_cache_key(self, request, view):
        if request.method != 'POST':
            return None
        email = (request.data.get('email') or '').strip().lower()
        if not email:
            return None  # no account named → only the IP throttle applies
        return self.cache_format % {'scope': self.scope, 'ident': email}
