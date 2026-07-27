import base64
import hashlib
import hmac
import json
import time
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings
from rest_framework.test import APIClient

from .models import User, UserRole


class UserModelTests(TestCase):
    def test_email_is_normalized_and_domain_is_enforced(self):
        user = User.objects.create_user(
            email="Agent@NVIDIA.COM",
            password="a-long-test-password",
        )
        self.assertEqual(user.email, "agent@nvidia.com")
        self.assertEqual(user.role, UserRole.AGENT)

        with self.assertRaises(ValidationError):
            User.objects.create_user(
                email="outside@example.com",
                password="a-long-test-password",
            )

    def test_team_role_has_ticket_rights_but_not_system_admin_rights(self):
        user = User.objects.create_user(
            email="team@nvidia.com",
            password="a-long-test-password",
            role=UserRole.TEAM,
        )
        self.assertTrue(user.can_manage_tickets)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)


class AuthenticationApiTests(TestCase):
    def setUp(self):
        self.password = "a-long-test-password"
        self.user = User.objects.create_user(
            email="agent@nvidia.com",
            password=self.password,
        )
        self.client = APIClient()

    def test_login_and_current_user(self):
        response = self.client.post(
            "/api/auth/login/",
            {"email": "AGENT@nvidia.com", "password": self.password},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["email"], "agent@nvidia.com")

        response = self.client.get("/api/auth/me/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["role"], UserRole.AGENT)

    def test_invalid_login_is_rejected(self):
        response = self.client.post(
            "/api/auth/login/",
            {"email": self.user.email, "password": "incorrect-password"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_login_requires_csrf_when_checks_are_enabled(self):
        csrf_client = APIClient(enforce_csrf_checks=True)
        response = csrf_client.post(
            "/api/auth/login/",
            {"email": self.user.email, "password": self.password},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

        csrf_response = csrf_client.get("/api/auth/csrf/")
        token = csrf_response.data["csrf_token"]
        response = csrf_client.post(
            "/api/auth/login/",
            {"email": self.user.email, "password": self.password},
            format="json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 200)

    def test_only_team_users_can_list_assignable_accounts(self):
        team_user = User.objects.create_user(
            email="team@nvidia.com",
            password=self.password,
            role=UserRole.TEAM,
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/auth/users/assignable/")
        self.assertEqual(response.status_code, 403)

        self.client.force_authenticate(user=team_user)
        response = self.client.get("/api/auth/users/assignable/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["email"], team_user.email)


@override_settings(
    APPSCRIPT_SSO_ENABLED=True,
    APPSCRIPT_SSO_URL="https://script.google.com/macros/s/test/exec",
    APPSCRIPT_SSO_SECRET="test-bridge-secret-that-is-more-than-32-characters",
    APPSCRIPT_SSO_ISSUER="nvgs-appscript",
    APPSCRIPT_SSO_AUDIENCE="nvgs-server",
    APPSCRIPT_SSO_AUTO_CREATE_USERS=True,
    APPSCRIPT_SSO_SUCCESS_REDIRECT="/api/auth/me/",
    APPSCRIPT_SSO_TOKEN_TTL_SECONDS=60,
    APPSCRIPT_SSO_STATE_TTL_SECONDS=300,
    APPSCRIPT_SSO_ONBOARDING_TTL_SECONDS=900,
    APPSCRIPT_SSO_CLOCK_SKEW_SECONDS=15,
    ALLOWED_EMAIL_DOMAINS=["nvidia.com"],
)
class AppsScriptSsoTests(TestCase):
    secret = "test-bridge-secret-that-is-more-than-32-characters"

    @staticmethod
    def _encode(value):
        raw = json.dumps(value, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    def _token(self, email, state, *, issued_at=None, secret=None):
        issued_at = issued_at or int(time.time())
        header_part = self._encode({"alg": "HS256", "typ": "JWT"})
        payload_part = self._encode(
            {
                "iss": "nvgs-appscript",
                "aud": "nvgs-server",
                "sub": email,
                "email": email,
                "state": state,
                "nonce": "12345678-1234-1234-1234-123456789012",
                "iat": issued_at,
                "exp": issued_at + 60,
            }
        )
        signing_input = f"{header_part}.{payload_part}"
        signature = hmac.new(
            (secret or self.secret).encode(),
            signing_input.encode(),
            hashlib.sha256,
        ).digest()
        signature_part = base64.urlsafe_b64encode(signature).decode().rstrip("=")
        return f"{signing_input}.{signature_part}"

    def _start(self, client):
        response = client.get("/api/auth/appscript/start/")
        self.assertEqual(response.status_code, 302)
        query = parse_qs(urlsplit(response["Location"]).query)
        self.assertEqual(query["nvgs_action"], ["login"])
        state = client.session["appscript_sso_state"]
        self.assertEqual(query["state"], [state])
        return state

    def _consume(self, client):
        response = client.get("/api/auth/appscript/consume/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("default-src 'none'", response["Content-Security-Policy"])
        self.assertNotIn("'unsafe-inline'", response["Content-Security-Policy"])
        return response

    def _post_callback(self, client, token):
        self._consume(client)
        return client.post(
            "/api/auth/appscript/callback/",
            {"token": token},
        )

    def _complete_onboarding(
        self,
        client,
        *,
        first_name="New",
        last_name="Agent",
        password="a-new-local-password-123",
    ):
        response = client.get("/api/auth/appscript/onboarding/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Never enter your NVIDIA or Google password")
        csrf_token = client.cookies["csrftoken"].value
        return client.post(
            "/api/auth/appscript/onboarding/",
            {
                "first_name": first_name,
                "last_name": last_name,
                "password1": password,
                "password2": password,
                "csrfmiddlewaretoken": csrf_token,
            },
        )

    def test_verified_user_completes_name_and_local_password_onboarding(self):
        client = Client(enforce_csrf_checks=True)
        state = self._start(client)
        response = self._post_callback(
            client,
            self._token("new.agent@nvidia.com", state),
        )

        self.assertRedirects(
            response,
            "/api/auth/appscript/onboarding/",
            fetch_redirect_response=False,
        )
        user = User.objects.get(email="new.agent@nvidia.com")
        self.assertEqual(user.role, UserRole.AGENT)
        self.assertFalse(user.has_usable_password())
        self.assertNotIn("_auth_user_id", client.session)

        tickets_response = client.get("/api/tickets/")
        self.assertEqual(tickets_response.status_code, 403)

        response = self._complete_onboarding(client)
        self.assertRedirects(
            response,
            "/api/auth/me/",
            fetch_redirect_response=False,
        )
        user.refresh_from_db()
        self.assertEqual(user.first_name, "New")
        self.assertEqual(user.last_name, "Agent")
        self.assertTrue(user.check_password("a-new-local-password-123"))
        self.assertIsNotNone(
            authenticate(
                email=user.email,
                password="a-new-local-password-123",
            )
        )

        me_response = client.get("/api/auth/me/")
        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(me_response.json()["email"], user.email)

    def test_bridge_callback_uses_signed_state_instead_of_generic_csrf_cookie(self):
        client = Client(enforce_csrf_checks=True)
        state = self._start(client)
        self._consume(client)
        self.assertNotIn("csrftoken", client.cookies)

        response = client.post(
            "/api/auth/appscript/callback/",
            {"token": self._token("agent@nvidia.com", state)},
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(email="agent@nvidia.com").exists())
        self.assertNotIn("_auth_user_id", client.session)

    def test_onboarding_form_keeps_normal_csrf_protection(self):
        client = Client(enforce_csrf_checks=True)
        state = self._start(client)
        self._post_callback(
            client,
            self._token("agent@nvidia.com", state),
        )

        response = client.post(
            "/api/auth/appscript/onboarding/",
            {
                "first_name": "Test",
                "last_name": "Agent",
                "password1": "a-new-local-password-123",
                "password2": "a-new-local-password-123",
            },
        )

        self.assertEqual(response.status_code, 403)

    def test_invalid_onboarding_password_is_not_saved(self):
        client = Client(enforce_csrf_checks=True)
        state = self._start(client)
        self._post_callback(
            client,
            self._token("agent@nvidia.com", state),
        )
        response = self._complete_onboarding(client, password="short")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "password is too short")
        user = User.objects.get(email="agent@nvidia.com")
        self.assertFalse(user.has_usable_password())

    def test_expired_onboarding_session_does_not_authenticate_user(self):
        client = Client(enforce_csrf_checks=True)
        state = self._start(client)
        self._post_callback(
            client,
            self._token("agent@nvidia.com", state),
        )
        session = client.session
        session["appscript_onboarding_started_at"] = int(time.time()) - 901
        session.save()

        response = client.get("/api/auth/appscript/onboarding/")

        self.assertEqual(response.status_code, 400)
        self.assertNotIn("_auth_user_id", client.session)

    def test_existing_team_role_is_preserved(self):
        user = User.objects.create_user(
            email="team@nvidia.com",
            password="a-long-test-password",
            role=UserRole.TEAM,
            first_name="Team",
            last_name="Member",
        )
        client = Client(enforce_csrf_checks=True)
        state = self._start(client)
        response = self._post_callback(
            client,
            self._token(user.email, state),
        )

        self.assertRedirects(
            response,
            "/api/auth/me/",
            fetch_redirect_response=False,
        )
        user.refresh_from_db()
        self.assertEqual(user.role, UserRole.TEAM)

    def test_bad_signature_is_rejected_and_state_is_consumed(self):
        client = Client(enforce_csrf_checks=True)
        state = self._start(client)
        token = self._token(
            "agent@nvidia.com",
            state,
            secret="incorrect-secret-that-is-still-long-enough",
        )
        response = self._post_callback(client, token)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(email="agent@nvidia.com").exists())

        response = client.post(
            "/api/auth/appscript/callback/",
            {"token": self._token("agent@nvidia.com", state)},
        )
        self.assertEqual(response.status_code, 400)

    def test_outside_domain_is_rejected(self):
        client = Client(enforce_csrf_checks=True)
        state = self._start(client)
        response = self._post_callback(
            client,
            self._token("outsider@example.com", state),
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(email="outsider@example.com").exists())

    def test_login_state_is_bound_to_the_browser_session(self):
        first_client = Client(enforce_csrf_checks=True)
        first_state = self._start(first_client)

        second_client = Client(enforce_csrf_checks=True)
        self._start(second_client)
        response = self._post_callback(
            second_client,
            self._token("agent@nvidia.com", first_state),
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(email="agent@nvidia.com").exists())

    def test_disabled_account_remains_blocked(self):
        user = User.objects.create_user(
            email="disabled@nvidia.com",
            password="a-long-test-password",
        )
        user.is_active = False
        user.save(update_fields=["is_active"])
        client = Client(enforce_csrf_checks=True)
        state = self._start(client)
        response = self._post_callback(
            client,
            self._token(user.email, state),
        )

        self.assertEqual(response.status_code, 403)
        self.assertNotIn("_auth_user_id", client.session)

    def test_expired_token_is_rejected(self):
        client = Client(enforce_csrf_checks=True)
        state = self._start(client)
        response = self._post_callback(
            client,
            self._token(
                "agent@nvidia.com",
                state,
                issued_at=int(time.time()) - 120,
            ),
        )

        self.assertEqual(response.status_code, 400)

    @override_settings(APPSCRIPT_SSO_AUTO_CREATE_USERS=False)
    def test_auto_creation_can_be_disabled(self):
        client = Client(enforce_csrf_checks=True)
        state = self._start(client)
        response = self._post_callback(
            client,
            self._token("unprovisioned@nvidia.com", state),
        )

        self.assertEqual(response.status_code, 403)
