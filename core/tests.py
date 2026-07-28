from django.test import TestCase

from accounts.models import User, UserRole


class HealthApiTests(TestCase):
    def test_health_reports_database_available(self):
        response = self.client.get("/api/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["database"], "available")

    def test_system_status_is_visible_to_team_but_not_agents(self):
        password = "a-long-test-password"
        agent = User.objects.create_user(
            email="status.agent@nvidia.com",
            password=password,
        )
        team_user = User.objects.create_user(
            email="status.team@nvidia.com",
            password=password,
            role=UserRole.TEAM,
        )

        self.client.force_login(agent)
        response = self.client.get("/api/system-status/")
        self.assertEqual(response.status_code, 403)

        self.client.force_login(team_user)
        response = self.client.get("/api/system-status/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["database"], "available")
        self.assertNotIn("webhook_url", response.json())
        self.assertIn("ticket_notification_mode", response.json())
        self.assertIn("ticket_notifications_configured", response.json())
