from unittest.mock import MagicMock, patch

import json

from django.core import mail
from django.core.management import call_command
from django.test import TestCase, override_settings

from accounts.models import User
from tickets.models import Ticket, TicketNotification


@override_settings(
    TICKET_NOTIFICATION_DELIVERY_MODE="webhook",
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


@override_settings(
    TICKET_NOTIFICATION_DELIVERY_MODE="email",
    TICKET_NOTIFICATION_EMAIL_TO=["power-automate@example.test"],
    TICKET_NOTIFICATION_EMAIL_TARGET_NAME="Robotics Ticket Chat",
    TICKET_NOTIFICATION_PUBLIC_BASE_URL="https://ticketing-system.local",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="nvgs@example.test",
)
class PowerAutomateEmailTests(TestCase):
    def test_worker_sends_original_power_automate_subject_and_json_shape(self):
        user = User.objects.create_user(
            email="email.agent@nvidia.com",
            password="a-long-test-password",
            first_name="Email",
            last_name="Agent",
        )
        ticket = Ticket.objects.create(
            reporter=user,
            created_by=user,
            title="Email flow compatibility",
            description="Synthetic.",
            workstation="Gear05",
        )
        notification = TicketNotification.objects.create(
            ticket=ticket,
            event_type="created",
            payload={
                "ticket_id": ticket.id,
                "reference": ticket.reference,
                "title": ticket.title,
                "description": ticket.description,
                "status": ticket.status,
                "priority": ticket.priority,
                "category": ticket.category,
                "workstation": ticket.workstation,
                "location": ticket.location,
                "reporter": user.display_name,
                "reporter_email": user.email,
                "assignee": "Unassigned",
                "assignee_email": "",
                "actor": user.display_name,
                "actor_email": user.email,
                "actor_role": user.role,
                "impact_level": "",
                "updated_at": ticket.updated_at.isoformat(),
                "downtime_start": ticket.downtime_start.isoformat(),
                "downtime_end": "",
                "downtime_minutes": None,
                "note": "",
                "ticket_path": f"/tickets/?ticket={ticket.id}",
            },
        )

        call_command("process_ticket_notifications", once=True)

        notification.refresh_from_db()
        self.assertIsNotNone(notification.sent_at)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(
            message.subject,
            f"GRTKT_EVENT TICKET_CREATED {ticket.reference}",
        )
        body = json.loads(message.body)
        self.assertEqual(body["app"], "GRTKT")
        self.assertEqual(body["eventType"], "TICKET_CREATED")
        self.assertEqual(body["ticket"]["requesterEmail"], user.email)
        self.assertEqual(
            body["ticketUrl"],
            f"https://ticketing-system.local/tickets/?ticket={ticket.id}",
        )
        self.assertEqual(body["teams"]["targetName"], "Robotics Ticket Chat")
