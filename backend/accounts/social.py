"""ID-token verification for social sign-in (Google today, Apple later).

The browser hands us the provider's ID token — a JWT signed with one of the
provider's rotating RSA keys. We verify it ourselves rather than calling a
provider "tokeninfo" endpoint per login: no round trip on the hot path, and no
dependence on a third-party endpoint's availability during sign-in.

Verification is deliberately strict. A token is only trusted when *all* of the
following hold:

* the signature checks out against the provider's published JWKS,
* `aud` equals our own client id (otherwise a token minted for any other Google
  app would authenticate here — this is the classic confused-deputy hole),
* `iss` is the provider's issuer,
* it hasn't expired,
* the email claim is present and marked verified by the provider.

The last one matters most: we link social identities to existing local accounts
by email, so an unverified address would let anyone who can set their provider
profile email take over a local account.
"""
import json
import threading
import time
import urllib.request

import jwt
from jwt import PyJWKClient

# How long a fetched JWKS stays usable before we re-fetch. Providers rotate keys
# every few days and publish the new one ahead of use, so this only needs to be
# short enough to pick up an emergency rotation.
JWKS_TTL_SECONDS = 60 * 60

_jwks_lock = threading.Lock()
_jwks_clients = {}  # url -> (PyJWKClient, fetched_at)


class SocialAuthError(Exception):
    """The token is missing, malformed, untrusted, or unusable."""


class Provider:
    """Everything that differs between one ID-token issuer and the next."""

    def __init__(self, key, issuers, jwks_url, client_id_setting):
        self.key = key
        self.issuers = issuers
        self.jwks_url = jwks_url
        self.client_id_setting = client_id_setting


GOOGLE = Provider(
    key='google',
    issuers=('https://accounts.google.com', 'accounts.google.com'),
    jwks_url='https://www.googleapis.com/oauth2/v3/certs',
    client_id_setting='GOOGLE_OAUTH_CLIENT_ID',
)

APPLE = Provider(
    key='apple',
    issuers=('https://appleid.apple.com',),
    jwks_url='https://appleid.apple.com/auth/keys',
    client_id_setting='APPLE_OAUTH_CLIENT_ID',
)

PROVIDERS = {p.key: p for p in (GOOGLE, APPLE)}


def _jwk_client(url):
    """A cached PyJWKClient per JWKS url.

    PyJWKClient does its own per-instance key caching, so the point of holding
    onto the instance is to avoid re-fetching the key set on every sign-in.
    """
    now = time.monotonic()
    with _jwks_lock:
        cached = _jwks_clients.get(url)
        if cached and now - cached[1] < JWKS_TTL_SECONDS:
            return cached[0]
        client = PyJWKClient(url, cache_keys=True, lifespan=JWKS_TTL_SECONDS)
        _jwks_clients[url] = (client, now)
        return client


def reset_jwks_cache():
    """Drop cached key sets — used by tests, and available for ops."""
    with _jwks_lock:
        _jwks_clients.clear()


def verify_id_token(provider, token, client_id):
    """Validate `token` and return its claims, or raise SocialAuthError.

    `client_id` is passed in (rather than read from settings here) so the caller
    owns the "is this provider even configured?" decision and can fail loudly.
    """
    if not token:
        raise SocialAuthError('No identity token was supplied.')
    if not client_id:
        raise SocialAuthError(f'{provider.key.title()} sign-in is not configured.')

    try:
        signing_key = _jwk_client(provider.jwks_url).get_signing_key_from_jwt(token)
    except Exception as exc:  # network failure, unknown kid, malformed header
        raise SocialAuthError('Could not verify that sign-in. Please try again.') from exc

    try:
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=['RS256', 'ES256'],
            audience=client_id,          # rejects tokens minted for other apps
            issuer=list(provider.issuers),
            options={'require': ['exp', 'iat', 'sub', 'aud', 'iss']},
        )
    except jwt.ExpiredSignatureError as exc:
        raise SocialAuthError('That sign-in has expired. Please try again.') from exc
    except jwt.InvalidTokenError as exc:
        raise SocialAuthError('That sign-in could not be verified.') from exc

    if not claims.get('sub'):
        raise SocialAuthError('That sign-in could not be verified.')
    return claims


def extract_identity(provider, claims):
    """Normalise provider claims into (uid, email, first_name, last_name).

    Raises if the provider didn't assert a *verified* email — we link accounts
    by address, so an unverified one is an account-takeover vector, not a
    cosmetic gap.
    """
    email = (claims.get('email') or '').strip()
    if not email:
        raise SocialAuthError('That account has no email address we can use.')

    # Google sends a real boolean; some providers stringify it. Apple always
    # verifies the address, and omits the claim on the private-relay path.
    verified = claims.get('email_verified', provider is APPLE)
    if isinstance(verified, str):
        verified = verified.lower() == 'true'
    if not verified:
        raise SocialAuthError(
            'Your email address is not verified with that provider. '
            'Verify it there, or sign in with your password.'
        )

    return {
        'uid': str(claims['sub']),
        'email': email,
        'first_name': (claims.get('given_name') or '').strip()[:80],
        'last_name': (claims.get('family_name') or '').strip()[:80],
    }


def fetch_jwks(url):
    """Raw JWKS fetch — used by the key client and available for diagnostics."""
    with urllib.request.urlopen(url, timeout=10) as resp:  # noqa: S310 (fixed https urls)
        return json.loads(resp.read().decode('utf-8'))
