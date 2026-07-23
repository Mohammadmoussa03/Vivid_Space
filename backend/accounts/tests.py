"""Auth-flow tests: httpOnly cookie transport, rotation, blacklist, CSRF, and
the security hardening (UUIDs, enumeration, password-reset revocation)."""
import time
from unittest import mock

import jwt
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from . import social
from .models import SocialAccount
from .tokens import email_verification_token

User = get_user_model()


class _StubJWKClient:
    """Stands in for PyJWKClient so tests never touch Google's JWKS endpoint.

    Returns the public half of the test keypair for any token, which keeps the
    real signature verification in play - only the key *fetch* is stubbed.
    """

    def __init__(self, private_key):
        self._key = private_key.public_key()

    def get_signing_key_from_jwt(self, token):
        return mock.Mock(key=self._key)

ACCESS = 'vs_access'
REFRESH = 'vs_refresh'


class CookieAuthTests(APITestCase):
    def setUp(self):
        self.password = 'S3cure-pass!'
        self.user = User.objects.create_user(
            email='member@example.com', password=self.password,
            is_approved=True, email_verified=True, role=User.Role.MEMBER,
        )

    def _csrf_headers(self):
        token = self.client.cookies.get('csrftoken')
        return {'HTTP_X_CSRFTOKEN': token.value} if token else {}

    def _login(self):
        return self.client.post(
            reverse('login'),
            {'email': self.user.email, 'password': self.password},
            format='json',
        )

    # --- core requirement: tokens only in httpOnly cookies, not the body ------
    def test_login_sets_httponly_cookies_and_hides_tokens(self):
        resp = self._login()
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        # Tokens must NOT appear in the JSON body.
        self.assertNotIn('access', resp.data)
        self.assertNotIn('refresh', resp.data)
        self.assertEqual(resp.data['user']['email'], self.user.email)
        # Cookies are set and flagged httpOnly.
        for name in (ACCESS, REFRESH):
            self.assertIn(name, resp.cookies)
            self.assertTrue(resp.cookies[name]['httponly'])

    def test_authenticated_request_uses_cookie(self):
        self._login()
        resp = self.client.get(reverse('me'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['email'], self.user.email)

    def test_no_cookie_is_unauthenticated(self):
        resp = self.client.get(reverse('me'))
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    # --- rotation + blacklist -------------------------------------------------
    def test_refresh_rotates_and_blacklists_old_token(self):
        self._login()
        old_refresh = self.client.cookies[REFRESH].value

        resp = self.client.post(reverse('token_refresh'), **self._csrf_headers())
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        new_refresh = resp.cookies[REFRESH].value
        self.assertNotEqual(old_refresh, new_refresh)

        # Replaying the consumed (old) refresh token must be rejected.
        self.client.cookies[REFRESH] = old_refresh
        replay = self.client.post(reverse('token_refresh'), **self._csrf_headers())
        self.assertEqual(replay.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_blacklists_refresh(self):
        self._login()
        old_refresh = self.client.cookies[REFRESH].value

        resp = self.client.post(reverse('logout'), **self._csrf_headers())
        self.assertEqual(resp.status_code, status.HTTP_205_RESET_CONTENT)

        # The blacklisted refresh token can no longer mint access tokens.
        self.client.cookies[REFRESH] = old_refresh
        after = self.client.post(reverse('token_refresh'), **self._csrf_headers())
        self.assertEqual(after.status_code, status.HTTP_401_UNAUTHORIZED)

    # --- CSRF (use a client that actually enforces it, like a real browser) ---
    def test_unsafe_request_without_csrf_is_rejected(self):
        client = APIClient(enforce_csrf_checks=True)
        client.post(reverse('login'),
                    {'email': self.user.email, 'password': self.password}, format='json')
        # Authenticated PATCH with a valid access cookie but no CSRF token.
        resp = client.patch(reverse('me'), {'first_name': 'X'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_unsafe_request_with_csrf_succeeds(self):
        client = APIClient(enforce_csrf_checks=True)
        client.post(reverse('login'),
                    {'email': self.user.email, 'password': self.password}, format='json')
        csrf = client.cookies['csrftoken'].value
        resp = client.patch(reverse('me'), {'first_name': 'Vivi'}, format='json',
                            HTTP_X_CSRFTOKEN=csrf)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['first_name'], 'Vivi')


class HardeningTests(APITestCase):
    def setUp(self):
        self.password = 'S3cure-pass!'
        self.user = User.objects.create_user(
            email='member@example.com', password=self.password,
            is_approved=True, email_verified=True, role=User.Role.MEMBER,
        )

    def _csrf_headers(self):
        token = self.client.cookies.get('csrftoken')
        return {'HTTP_X_CSRFTOKEN': token.value} if token else {}

    # --- UUID -----------------------------------------------------------------
    def test_users_have_unique_uuid_exposed(self):
        other = User.objects.create_user(email='b@example.com', password='x', is_approved=True)
        self.assertIsNotNone(self.user.uuid)
        self.assertNotEqual(self.user.uuid, other.uuid)
        resp = self.client.post(
            reverse('login'), {'email': self.user.email, 'password': self.password}, format='json')
        self.assertEqual(str(self.user.uuid), resp.data['user']['uuid'])

    # --- registration enumeration ---------------------------------------------
    def test_registration_response_is_identical_for_new_and_existing_email(self):
        new = self.client.post(reverse('register'), {
            'email': 'fresh@example.com', 'password': 'S3cure-pass!',
            'first_name': 'A', 'last_name': 'B',
        }, format='json')
        existing = self.client.post(reverse('register'), {
            'email': self.user.email, 'password': 'S3cure-pass!',
            'first_name': 'A', 'last_name': 'B',
        }, format='json')
        self.assertEqual(new.status_code, existing.status_code)
        self.assertEqual(new.data, existing.data)
        # No token/user leak, and no duplicate account created.
        self.assertNotIn('user', new.data)
        self.assertEqual(User.objects.filter(email=self.user.email).count(), 1)

    # --- password reset revokes existing sessions -----------------------------
    def test_password_reset_blacklists_existing_tokens(self):
        self.client.post(
            reverse('login'), {'email': self.user.email, 'password': self.password}, format='json')
        old_refresh = self.client.cookies[REFRESH].value

        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        resp = self.client.post(reverse('password_reset_confirm'), {
            'uid': uid, 'token': token, 'password': 'Brand-New-Pass9',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        # The pre-reset refresh token must no longer work.
        self.client.cookies[REFRESH] = old_refresh
        after = self.client.post(reverse('token_refresh'), **self._csrf_headers())
        self.assertEqual(after.status_code, status.HTTP_401_UNAUTHORIZED)

    # --- URL scheme validation (anti stored-XSS) ------------------------------
    def test_safe_url_validator_rejects_script_schemes(self):
        from rest_framework.serializers import ValidationError

        from bookings.serializers import validate_safe_url

        for good in ('https://maps.google.com/x', 'http://a.b', '/media/x.png', ''):
            self.assertEqual(validate_safe_url(good), good)
        for bad in ('javascript:alert(1)', 'data:text/html,x', 'vbscript:x'):
            with self.assertRaises(ValidationError):
                validate_safe_url(bad)

    # --- admin user-create is blocked (not a 500) -----------------------------
    def test_admin_user_create_is_method_not_allowed(self):
        admin = User.objects.create_user(
            email='admin@example.com', password='adminpass', is_approved=True,
            email_verified=True, role=User.Role.ADMIN)
        self.client.post(
            reverse('login'), {'email': admin.email, 'password': 'adminpass'}, format='json')
        resp = self.client.post(reverse('admin-user-list'), {'email': 'x@y.com'},
                                format='json', **self._csrf_headers())
        self.assertEqual(resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class EmailVerificationTests(APITestCase):
    """Signup is gated on confirming the emailed link — no admin approval step."""

    PASSWORD = 'S3cure-pass!'
    EMAIL = 'newbie@example.com'

    def _register(self):
        return self.client.post(reverse('register'), {
            'email': self.EMAIL, 'password': self.PASSWORD,
            'first_name': 'New', 'last_name': 'Bie',
        }, format='json')

    def _login(self):
        return self.client.post(reverse('login'), {
            'email': self.EMAIL, 'password': self.PASSWORD,
        }, format='json')

    def _link_parts(self, user):
        return (urlsafe_base64_encode(force_bytes(user.pk)),
                email_verification_token.make_token(user))

    def test_signup_is_approved_but_unverified_and_cannot_login(self):
        self.assertEqual(self._register().status_code, status.HTTP_201_CREATED)
        u = User.objects.get(email=self.EMAIL)
        self.assertTrue(u.is_approved)      # no admin gate
        self.assertFalse(u.email_verified)  # but the email gate is closed
        self.assertEqual(self._login().status_code, status.HTTP_400_BAD_REQUEST)

    def test_registration_emails_a_working_confirmation_link(self):
        self._register()
        self.assertEqual(len(mail.outbox), 1)
        u = User.objects.get(email=self.EMAIL)
        # The link the member actually receives carries a valid token.
        self.assertIn(f'verify_uid={urlsafe_base64_encode(force_bytes(u.pk))}',
                      mail.outbox[0].body)

    def test_verifying_then_logging_in_succeeds(self):
        self._register()
        uid, token = self._link_parts(User.objects.get(email=self.EMAIL))
        resp = self.client.post(reverse('verify_email'), {'uid': uid, 'token': token},
                                format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(User.objects.get(email=self.EMAIL).email_verified)
        self.assertEqual(self._login().status_code, status.HTTP_200_OK)

    def test_bad_token_is_rejected(self):
        self._register()
        uid, _ = self._link_parts(User.objects.get(email=self.EMAIL))
        resp = self.client.post(reverse('verify_email'), {'uid': uid, 'token': 'nope'},
                                format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.get(email=self.EMAIL).email_verified)

    def test_password_reset_token_cannot_confirm_an_email(self):
        """The two link types use different salts and must not be interchangeable."""
        self._register()
        u = User.objects.get(email=self.EMAIL)
        uid = urlsafe_base64_encode(force_bytes(u.pk))
        resp = self.client.post(
            reverse('verify_email'),
            {'uid': uid, 'token': default_token_generator.make_token(u)}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_link_is_single_use_but_replay_reads_as_success(self):
        self._register()
        uid, token = self._link_parts(User.objects.get(email=self.EMAIL))
        self.client.post(reverse('verify_email'), {'uid': uid, 'token': token}, format='json')
        again = self.client.post(reverse('verify_email'), {'uid': uid, 'token': token},
                                 format='json')
        self.assertEqual(again.status_code, status.HTTP_200_OK)
        self.assertIn('already confirmed', again.data['detail'])

    def test_resend_is_silent_for_unknown_and_verified_addresses(self):
        self._register()
        mail.outbox.clear()
        unknown = self.client.post(reverse('resend_verification'),
                                   {'email': 'ghost@example.com'}, format='json')
        self.assertEqual(unknown.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 0)

        # A real unverified account does get a fresh link...
        pending = self.client.post(reverse('resend_verification'),
                                   {'email': self.EMAIL}, format='json')
        self.assertEqual(len(mail.outbox), 1)

        # ...but the same request for a verified one is a no-op with an
        # identical response, so it can't be used to probe account state.
        User.objects.filter(email=self.EMAIL).update(email_verified=True)
        mail.outbox.clear()
        verified = self.client.post(reverse('resend_verification'),
                                    {'email': self.EMAIL}, format='json')
        self.assertEqual(len(mail.outbox), 0)
        self.assertEqual(pending.data, verified.data)

    def test_admins_are_exempt_from_the_gate(self):
        User.objects.create_user(email='boss@example.com', password=self.PASSWORD,
                                 is_approved=True, email_verified=False,
                                 role=User.Role.ADMIN)
        resp = self.client.post(reverse('login'), {
            'email': 'boss@example.com', 'password': self.PASSWORD}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


class EmailCaseInsensitivityTests(APITestCase):
    """Email is the credential: capitalisation must never split an account."""

    PASSWORD = 'S3cure-pass!'

    def setUp(self):
        self.user = User.objects.create_user(
            email='Casey@Example.COM', password=self.PASSWORD,
            is_approved=True, email_verified=True, role=User.Role.MEMBER,
        )

    def test_stored_email_is_canonicalised_on_write(self):
        self.assertEqual(self.user.email, 'casey@example.com')
        # Direct assignment + save (django-admin / shell path) normalises too.
        self.user.email = '  MiXeD@Example.com '
        self.user.save()
        self.assertEqual(User.objects.get(pk=self.user.pk).email, 'mixed@example.com')

    def test_login_accepts_any_capitalisation(self):
        for typed in ('casey@example.com', 'Casey@Example.COM', ' CASEY@EXAMPLE.COM '):
            resp = self.client.post(reverse('login'),
                                    {'email': typed, 'password': self.PASSWORD},
                                    format='json')
            self.assertEqual(resp.status_code, status.HTTP_200_OK, typed)

    def test_registration_normalises_and_cannot_duplicate_by_case(self):
        resp = self.client.post(reverse('register'), {
            'email': '  NewBie@Example.COM ', 'password': self.PASSWORD,
            'first_name': 'New', 'last_name': 'Bie',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(email='newbie@example.com').exists())

        # A second signup that differs only in case is the existing-account
        # path, not a new row (and stays non-enumerating).
        mail.outbox.clear()
        again = self.client.post(reverse('register'), {
            'email': 'NEWBIE@example.com', 'password': self.PASSWORD,
            'first_name': 'Imp', 'last_name': 'Ostor',
        }, format='json')
        self.assertEqual(again.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.filter(email__iexact='newbie@example.com').count(), 1)

    def test_password_reset_and_resend_find_the_account_by_any_case(self):
        mail.outbox.clear()
        self.client.post(reverse('password_reset'),
                         {'email': 'CASEY@example.com'}, format='json')
        self.assertEqual(len(mail.outbox), 1)

        User.objects.filter(pk=self.user.pk).update(email_verified=False)
        mail.outbox.clear()
        self.client.post(reverse('resend_verification'),
                         {'email': 'Casey@EXAMPLE.com'}, format='json')
        self.assertEqual(len(mail.outbox), 1)

    def test_profile_update_rejects_an_email_taken_in_another_case(self):
        other = User.objects.create_user(
            email='taken@example.com', password=self.PASSWORD,
            is_approved=True, email_verified=True, role=User.Role.MEMBER,
        )
        self.client.force_authenticate(user=self.user)
        resp = self.client.patch(reverse('me'), {'email': 'TAKEN@Example.com'},
                                 format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(User.objects.get(pk=other.pk).email, 'taken@example.com')

    def test_profile_update_stores_the_lowercase_form(self):
        self.client.force_authenticate(user=self.user)
        resp = self.client.patch(reverse('me'), {'email': 'Casey.New@Example.COM'},
                                 format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(User.objects.get(pk=self.user.pk).email, 'casey.new@example.com')


class GoogleSignInTests(APITestCase):
    """Google sign-in: real RS256 verification against a stubbed JWKS.

    The token is signed with a throwaway keypair and PyJWKClient is pointed at
    it, so these exercise the actual signature/`aud`/`iss`/expiry path rather
    than mocking the verifier out.
    """

    CLIENT_ID = 'test-client-id.apps.googleusercontent.com'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from cryptography.hazmat.primitives.asymmetric import rsa
        cls.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def setUp(self):
        social.reset_jwks_cache()
        patcher = mock.patch.object(
            social, '_jwk_client', return_value=_StubJWKClient(self.private_key))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(social.reset_jwks_cache)

    def _token(self, **overrides):
        now = int(time.time())
        claims = {
            'iss': 'https://accounts.google.com',
            'aud': self.CLIENT_ID,
            'sub': '1234567890',
            'email': 'Gina@Example.com',
            'email_verified': True,
            'given_name': 'Gina',
            'family_name': 'Ng',
            'iat': now,
            'exp': now + 3600,
        }
        claims.update(overrides)
        return jwt.encode(claims, self.private_key, algorithm='RS256')

    def _post(self, token):
        return self.client.post(reverse('social_google'), {'credential': token},
                                format='json')

    # --- happy paths ---------------------------------------------------------

    def test_new_user_is_created_verified_and_signed_in(self):
        with override_settings(GOOGLE_OAUTH_CLIENT_ID=self.CLIENT_ID):
            resp = self._post(self._token())
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(resp.data['created'])

        user = User.objects.get(email='gina@example.com')   # normalised
        self.assertTrue(user.email_verified)   # provider vouched for it
        self.assertTrue(user.is_approved)
        self.assertEqual(user.first_name, 'Gina')
        self.assertFalse(user.has_usable_password())
        self.assertEqual(user.social_accounts.get().provider_uid, '1234567890')

        # Same session transport as a password login: httpOnly cookies, no
        # tokens in the body.
        self.assertTrue(resp.cookies[ACCESS]['httponly'])
        self.assertTrue(resp.cookies[REFRESH]['httponly'])
        self.assertNotIn('access', resp.data)

    def test_returning_user_is_matched_by_subject_not_email(self):
        with override_settings(GOOGLE_OAUTH_CLIENT_ID=self.CLIENT_ID):
            self._post(self._token())
            # Same `sub`, address changed at Google — still the same account.
            again = self._post(self._token(email='gina.ng@example.com'))
        self.assertEqual(again.status_code, status.HTTP_200_OK)
        self.assertFalse(again.data['created'])
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(SocialAccount.objects.count(), 1)

    def test_links_to_an_existing_password_account_with_the_same_email(self):
        existing = User.objects.create_user(
            email='gina@example.com', password='S3cure-pass!',
            is_approved=True, email_verified=True, role=User.Role.MEMBER)
        with override_settings(GOOGLE_OAUTH_CLIENT_ID=self.CLIENT_ID):
            resp = self._post(self._token())
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data['created'])
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(existing.social_accounts.count(), 1)
        # The password still works — linking adds a way in, it doesn't replace one.
        existing.refresh_from_db()
        self.assertTrue(existing.check_password('S3cure-pass!'))

    def test_google_settles_a_never_confirmed_signup(self):
        User.objects.create_user(email='gina@example.com', password='S3cure-pass!',
                                 is_approved=True, email_verified=False,
                                 role=User.Role.MEMBER)
        with override_settings(GOOGLE_OAUTH_CLIENT_ID=self.CLIENT_ID):
            self._post(self._token())
        self.assertTrue(User.objects.get(email='gina@example.com').email_verified)

    # --- rejections ----------------------------------------------------------

    def test_token_for_another_client_id_is_rejected(self):
        """The confused-deputy case: a valid Google token minted for a different app."""
        with override_settings(GOOGLE_OAUTH_CLIENT_ID=self.CLIENT_ID):
            resp = self._post(self._token(aud='someone-elses-app.apps.googleusercontent.com'))
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(User.objects.count(), 0)

    def test_unverified_email_is_rejected(self):
        with override_settings(GOOGLE_OAUTH_CLIENT_ID=self.CLIENT_ID):
            resp = self._post(self._token(email_verified=False))
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(User.objects.count(), 0)

    def test_expired_token_is_rejected(self):
        now = int(time.time())
        with override_settings(GOOGLE_OAUTH_CLIENT_ID=self.CLIENT_ID):
            resp = self._post(self._token(iat=now - 7200, exp=now - 3600))
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_token_signed_by_the_wrong_key_is_rejected(self):
        from cryptography.hazmat.primitives.asymmetric import rsa
        attacker = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        now = int(time.time())
        forged = jwt.encode({
            'iss': 'https://accounts.google.com', 'aud': self.CLIENT_ID,
            'sub': 'attacker', 'email': 'admin@example.com', 'email_verified': True,
            'iat': now, 'exp': now + 3600,
        }, attacker, algorithm='RS256')
        with override_settings(GOOGLE_OAUTH_CLIENT_ID=self.CLIENT_ID):
            resp = self._post(forged)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(User.objects.count(), 0)

    def test_wrong_issuer_is_rejected(self):
        with override_settings(GOOGLE_OAUTH_CLIENT_ID=self.CLIENT_ID):
            resp = self._post(self._token(iss='https://evil.example.com'))
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_endpoint_is_inert_when_not_configured(self):
        with override_settings(GOOGLE_OAUTH_CLIENT_ID=''):
            resp = self._post(self._token())
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(User.objects.count(), 0)

    def test_deactivated_account_cannot_sign_in_with_google(self):
        User.objects.create_user(email='gina@example.com', password='S3cure-pass!',
                                 is_approved=True, email_verified=True,
                                 is_active=False, role=User.Role.MEMBER)
        with override_settings(GOOGLE_OAUTH_CLIENT_ID=self.CLIENT_ID):
            resp = self._post(self._token())
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)


class BrandedEmailTests(APITestCase):
    """Every outgoing email carries the logo and a plain-text fallback."""

    def _send(self, body='Hi there,\n\nVisit https://vividspace.space/ to continue.\n'):
        from config.mail import send_branded_mail
        send_branded_mail('Subject line', body, 'casey@example.com')
        return mail.outbox[-1]

    def test_message_has_text_and_html_parts_with_an_inline_logo(self):
        msg = self._send()
        self.assertEqual([mime for _, mime in msg.alternatives], ['text/html'])
        # multipart/related is what makes the cid: reference resolve in-body
        # rather than showing up as a downloadable attachment.
        self.assertEqual(msg.message().get_content_type(), 'multipart/related')

        images = [p for p in msg.message().walk() if p.get_content_type() == 'image/png']
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0].get('Content-ID'), '<vividspace-logo>')
        self.assertIn('inline', images[0].get('Content-Disposition'))
        self.assertIn('src="cid:vividspace-logo"', msg.alternatives[0][0])

    def test_plain_text_body_is_preserved_verbatim(self):
        """Text-only clients must still get exactly what they got before."""
        body = 'Hi there,\n\nVisit https://vividspace.space/ to continue.\n'
        self.assertEqual(self._send(body).body, body)

    def test_urls_become_clickable_and_content_is_escaped(self):
        msg = self._send('Reset: https://vividspace.space/?a=1&b=2\n\n<script>x</script>')
        html = msg.alternatives[0][0]
        self.assertIn('href="https://vividspace.space/?a=1&amp;b=2"', html)
        # Body text is escaped, so a stray angle bracket can't inject markup.
        self.assertNotIn('<script>', html)
        self.assertIn('&lt;script&gt;', html)

    def test_real_transactional_emails_are_branded(self):
        """Spot-check a live send path rather than only the helper."""
        user = User.objects.create_user(email='casey@example.com', password='S3cure-pass!',
                                        is_approved=True, email_verified=True)
        mail.outbox.clear()
        from accounts.emails import send_password_reset
        send_password_reset(user)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('src="cid:vividspace-logo"', mail.outbox[0].alternatives[0][0])

    def test_missing_logo_degrades_to_a_plain_send(self):
        """A missing asset must not break the request that triggered the email."""
        from config import mail as mail_mod
        mail_mod._logo_bytes.cache_clear()
        self.addCleanup(mail_mod._logo_bytes.cache_clear)
        with mock.patch.object(mail_mod, 'LOGO_PATH', mail_mod.LOGO_PATH.parent / 'nope.png'):
            msg = self._send()
        self.assertEqual(len(msg.attachments), 0)
        self.assertNotIn('cid:', msg.alternatives[0][0])
        self.assertTrue(msg.body)   # the text email still goes out

    def test_no_recipient_is_a_no_op(self):
        from config.mail import send_branded_mail
        mail.outbox.clear()
        self.assertEqual(send_branded_mail('s', 'b', ''), 0)
        self.assertEqual(send_branded_mail('s', 'b', []), 0)
        self.assertEqual(len(mail.outbox), 0)
