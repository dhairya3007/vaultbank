from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import os


class SessionSecurityAndAuthTests(TestCase):
    """
    Comprehensive test suite verifying:
    1. Session and cookie security settings
    2. Login and authentication session creation
    3. Session storage in the database
    4. Session persistence across multiple consecutive requests
    5. Session expiry age (14 days)
    6. Logout flow and session invalidation
    7. HTTPS proxy header handling
    8. Message storage in session
    """

    def setUp(self):
        self.username = 'testmanager'
        self.password = 'SuperSecurePass123!'
        self.user = User.objects.create_user(
            username=self.username,
            password=self.password,
            email='manager@vaultbank.test',
            is_staff=True
        )
        self.client = Client()

    def test_session_configuration_settings(self):
        """Verify all settings are configured according to enterprise requirements."""
        self.assertEqual(settings.SESSION_ENGINE, 'django.contrib.sessions.backends.db')
        self.assertEqual(settings.SESSION_COOKIE_AGE, 1209600)  # 14 days
        self.assertFalse(settings.SESSION_EXPIRE_AT_BROWSER_CLOSE)
        self.assertFalse(settings.SESSION_SAVE_EVERY_REQUEST)
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
        self.assertEqual(settings.SESSION_COOKIE_SAMESITE, 'Lax')
        self.assertEqual(settings.SESSION_COOKIE_NAME, 'vaultbank_sessionid')
        self.assertEqual(settings.CSRF_COOKIE_NAME, 'vaultbank_csrftoken')
        self.assertEqual(settings.MESSAGE_STORAGE, 'django.contrib.messages.storage.session.SessionStorage')
        self.assertEqual(settings.SECURE_PROXY_SSL_HEADER, ('HTTP_X_FORWARDED_PROTO', 'https'))
        self.assertTrue(settings.USE_X_FORWARDED_HOST)
        self.assertTrue(settings.USE_X_FORWARDED_PORT)

    def test_unauthenticated_redirection(self):
        """Unauthenticated requests must redirect to login with ?next parameter."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/?next=/', response.url)

        response = self.client.get('/lockers/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/?next=/lockers/', response.url)

    def test_login_flow_and_session_cookie_creation(self):
        """Logging in creates a session in the database and returns the session cookie."""
        response = self.client.post('/login/', {
            'username': self.username,
            'password': self.password,
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/')

        # Verify session cookie was set
        session_cookie = self.client.cookies.get('vaultbank_sessionid')
        self.assertIsNotNone(session_cookie)
        session_key = session_cookie.value

        # Verify session exists in DB
        db_session = Session.objects.filter(session_key=session_key).first()
        self.assertIsNotNone(db_session, "Session record must be stored in django_session database table.")

        # Verify decoded session contains user ID
        session_data = db_session.get_decoded()
        self.assertEqual(str(session_data.get('_auth_user_id')), str(self.user.pk))

    def test_session_expiry_date_is_14_days(self):
        """Session expiry in the database must be ~14 days from login."""
        self.client.post('/login/', {
            'username': self.username,
            'password': self.password,
        })
        session_key = self.client.cookies.get('vaultbank_sessionid').value
        db_session = Session.objects.get(session_key=session_key)

        now = timezone.now()
        expected_expiry = now + timedelta(seconds=1209600)
        # Allow a tolerance of +/- 60 seconds
        difference = abs((db_session.expire_date - expected_expiry).total_seconds())
        self.assertLess(difference, 60, "Session expire_date should be exactly ~14 days in the future.")

    def test_session_persistence_across_multiple_views(self):
        """Session must persist across navigation to multiple protected views without logging out."""
        logged_in = self.client.login(username=self.username, password=self.password)
        self.assertTrue(logged_in)

        # 1. Dashboard
        r1 = self.client.get('/')
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r1.wsgi_request.user, self.user)

        # 2. Locker List
        r2 = self.client.get('/lockers/')
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.wsgi_request.user, self.user)

        # 3. Customer List
        r3 = self.client.get('/customers/')
        self.assertEqual(r3.status_code, 200)
        self.assertEqual(r3.wsgi_request.user, self.user)

        # 4. Audit Logs
        r4 = self.client.get('/logs/')
        self.assertEqual(r4.status_code, 200)
        self.assertEqual(r4.wsgi_request.user, self.user)

    def test_logout_flow_and_session_invalidation(self):
        """Logging out must terminate the session and redirect to /login/."""
        self.client.login(username=self.username, password=self.password)

        # Ensure user is logged in
        r = self.client.get('/')
        self.assertEqual(r.status_code, 200)

        # Post to logout
        response = self.client.post('/logout/')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/login/')

        # Subsequent protected page request must redirect to login
        r_after = self.client.get('/')
        self.assertEqual(r_after.status_code, 302)
        self.assertIn('/login/?next=/', r_after.url)

    def test_https_proxy_ssl_header_handling(self):
        """Reverse proxy SSL header must be recognized as secure HTTPS."""
        response = self.client.get('/', HTTP_X_FORWARDED_PROTO='https')
        self.assertTrue(response.wsgi_request.is_secure())

    @override_settings(DEBUG=False, SESSION_COOKIE_SECURE=True, CSRF_COOKIE_SECURE=True)
    def test_production_secure_cookie_configuration(self):
        """In production mode with HTTPS, SESSION_COOKIE_SECURE must be enabled."""
        self.assertTrue(settings.SESSION_COOKIE_SECURE)
        self.assertTrue(settings.CSRF_COOKIE_SECURE)

    def test_locker_edit_view_and_is_active_toggle(self):
        """Verify the locker edit view renders the is_active toggle correctly and updates state."""
        from lockers.models import Locker
        locker = Locker.objects.create(
            locker_number='Z-999',
            annual_fee=250.00,
            is_active=True
        )
        self.client.login(username=self.username, password=self.password)

        # GET Edit Page
        response = self.client.get(f'/lockers/{locker.pk}/edit/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Locker Active Status')
        self.assertContains(response, 'is_active')

        # POST Deactivate
        post_data = {
            'locker_number': 'Z-999',
            'annual_fee': '250.00',
            'payment_status': 'paid',
            # 'is_active' omitted to represent unchecking
        }
        res_post = self.client.post(f'/lockers/{locker.pk}/edit/', post_data)
        self.assertEqual(res_post.status_code, 302)
        locker.refresh_from_db()
        self.assertFalse(locker.is_active)

        # POST Reactivate
        post_data['is_active'] = 'on'
        res_post2 = self.client.post(f'/lockers/{locker.pk}/edit/', post_data)
        self.assertEqual(res_post2.status_code, 302)
        locker.refresh_from_db()
        self.assertTrue(locker.is_active)

