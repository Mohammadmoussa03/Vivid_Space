"""Auth-flow tests: httpOnly cookie transport, rotation, blacklist, CSRF, and
the security hardening (UUIDs, enumeration, password-reset revocation)."""
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

User = get_user_model()

ACCESS = 'vs_access'
REFRESH = 'vs_refresh'


class CookieAuthTests(APITestCase):
    def setUp(self):
        self.password = 'S3cure-pass!'
        self.user = User.objects.create_user(
            email='member@example.com', password=self.password,
            is_approved=True, role=User.Role.MEMBER,
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
            is_approved=True, role=User.Role.MEMBER,
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
            email='admin@example.com', password='adminpass', is_approved=True, role=User.Role.ADMIN)
        self.client.post(
            reverse('login'), {'email': admin.email, 'password': 'adminpass'}, format='json')
        resp = self.client.post(reverse('admin-user-list'), {'email': 'x@y.com'},
                                format='json', **self._csrf_headers())
        self.assertEqual(resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class RegistrationApprovalTests(APITestCase):
    def test_new_user_is_auto_approved_and_can_login(self):
        r = self.client.post(reverse('register'), {
            'email': 'newbie@example.com', 'password': 'S3cure-pass!',
            'first_name': 'New', 'last_name': 'Bie',
        }, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        u = User.objects.get(email='newbie@example.com')
        self.assertTrue(u.is_approved)
        # Can log in immediately (no admin approval gate).
        login = self.client.post(reverse('login'), {
            'email': 'newbie@example.com', 'password': 'S3cure-pass!',
        }, format='json')
        self.assertEqual(login.status_code, status.HTTP_200_OK)
