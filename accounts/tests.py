from django.core.exceptions import ValidationError
from django.test import TestCase
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
