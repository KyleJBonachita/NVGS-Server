from django.test import TestCase


class HealthApiTests(TestCase):
    def test_health_reports_database_available(self):
        response = self.client.get("/api/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["database"], "available")

