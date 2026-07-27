from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.test import TestCase, override_settings

from accounts.models import User
from tickets.models import Ticket, TicketNotification


@override_settings(
    TICKET_NOTIFICATION_WEBHOOK_URL="https://notifications.example.test/hook",
)
class NotificationWorkerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="notification.agent@nvidia.com",
            password="a-long-test-password",
        )
        self.ticket = Ticket.objects.create(
            reporter=self.user,
            created_by=self.user,
            title="Notification delivery",
            description="Synthetic.",
        )
        self.notification = TicketNotification.objects.create(
            ticket=self.ticket,
            event_type="created",
            payload={
                "ticket_id": self.ticket.id,
                "reference": self.ticket.reference,
                "title": self.ticket.title,
                "status": self.ticket.status,
                "priority": self.ticket.priority,
                "reporter": self.user.display_name,
                "assignee": "Unassigned",
                "actor": self.user.display_name,
                "note": "",
                "ticket_path": f"/tickets/?ticket={self.ticket.id}",
            },
        )

    @patch("tickets.notifications.urllib.request.urlopen")
    def test_worker_marks_successful_notification_sent(self, urlopen):
        response = MagicMock()
        response.status = 200
        urlopen.return_value.__enter__.return_value = response

        call_command("process_ticket_notifications", once=True)

        self.notification.refresh_from_db()
        self.assertIsNotNone(self.notification.sent_at)
        self.assertEqual(self.notification.attempts, 1)

    @patch(
        "tickets.notifications.urllib.request.urlopen",
        side_effect=OSError("synthetic outage"),
    )
    def test_worker_retries_without_losing_notification(self, _urlopen):
        call_command("process_ticket_notifications", once=True)

        self.notification.refresh_from_db()
        self.assertIsNone(self.notification.sent_at)
        self.assertEqual(self.notification.attempts, 1)
        self.assertIn("OSError", self.notification.last_error)
