import csv
import io
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.management import CommandError, call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.models import User, UserRole

from .models import (
    Ticket,
    TicketComment,
    TicketEvent,
    TicketNotification,
    TicketPriority,
    TicketStatus,
)


class TicketAccessTests(APITestCase):
    def setUp(self):
        password = "a-long-test-password"
        self.agent_one = User.objects.create_user(
            email="agent.one@nvidia.com",
            password=password,
        )
        self.agent_two = User.objects.create_user(
            email="agent.two@nvidia.com",
            password=password,
        )
        self.team_user = User.objects.create_user(
            email="tech.team@nvidia.com",
            password=password,
            role=UserRole.TEAM,
        )
        self.agent_one_ticket = Ticket.objects.create(
            reporter=self.agent_one,
            created_by=self.agent_one,
            title="Robot console issue",
            description="The console does not load.",
        )
        self.agent_two_ticket = Ticket.objects.create(
            reporter=self.agent_two,
            created_by=self.agent_two,
            title="Keyboard issue",
            description="Several keys do not respond.",
        )

    def authenticate(self, user):
        self.client.force_authenticate(user=user)

    def test_agent_sees_only_their_own_tickets(self):
        self.authenticate(self.agent_one)
        response = self.client.get(reverse("ticket-list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["id"],
            self.agent_one_ticket.id,
        )

        response = self.client.get(
            reverse("ticket-detail", args=[self.agent_two_ticket.id])
        )
        self.assertEqual(response.status_code, 404)

    def test_agent_can_choose_priority_but_cannot_self_assign_or_set_status(self):
        self.authenticate(self.agent_one)
        response = self.client.post(
            reverse("ticket-list"),
            {
                "title": "Application error",
                "description": "The robotics application displays an error.",
                "category": "Others",
                "priority": TicketPriority.URGENT,
                "status": TicketStatus.RESOLVED,
                "resolution_notes": "Untrusted client-provided resolution",
                "assignee": 999999,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        ticket = Ticket.objects.get(pk=response.data["id"])
        self.assertEqual(ticket.reporter, self.agent_one)
        self.assertEqual(ticket.created_by, self.agent_one)
        self.assertEqual(ticket.priority, TicketPriority.URGENT)
        self.assertEqual(ticket.status, TicketStatus.OPEN)
        self.assertIsNone(ticket.assignee)
        self.assertEqual(ticket.resolution_notes, "")
        self.assertTrue(
            TicketEvent.objects.filter(ticket=ticket, action="created").exists()
        )

    def test_ticket_reporter_cannot_be_changed_after_creation(self):
        self.authenticate(self.team_user)
        response = self.client.patch(
            reverse("ticket-detail", args=[self.agent_one_ticket.id]),
            {"reporter_id": self.agent_two.id},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.agent_one_ticket.refresh_from_db()
        self.assertEqual(self.agent_one_ticket.reporter, self.agent_one)

    def test_agent_cannot_update_ticket(self):
        self.authenticate(self.agent_one)
        response = self.client.patch(
            reverse("ticket-detail", args=[self.agent_one_ticket.id]),
            {"status": TicketStatus.CLOSED, "resolution_notes": "Done"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_team_can_see_and_manage_all_tickets(self):
        self.authenticate(self.team_user)
        response = self.client.get(reverse("ticket-list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)

        response = self.client.post(
            reverse("ticket-assign", args=[self.agent_one_ticket.id]),
            {"assignee": self.team_user.id},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], TicketStatus.ASSIGNED)

        response = self.client.post(
            reverse("ticket-transition", args=[self.agent_one_ticket.id]),
            {"status": TicketStatus.IN_PROGRESS},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        response = self.client.post(
            reverse("ticket-transition", args=[self.agent_one_ticket.id]),
            {
                "status": TicketStatus.RESOLVED,
                "resolution_notes": "Restarted the robotics console service.",
                "root_cause": "Software Bug",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.agent_one_ticket.refresh_from_db()
        self.assertEqual(self.agent_one_ticket.assignee, self.team_user)
        self.assertEqual(self.agent_one_ticket.status, TicketStatus.RESOLVED)
        self.assertIsNotNone(self.agent_one_ticket.resolved_at)
        self.assertEqual(self.agent_one_ticket.resolved_by, self.team_user)
        self.assertTrue(
            TicketEvent.objects.filter(
                ticket=self.agent_one_ticket,
                action="status_changed",
            ).exists()
        )

    def test_resolution_is_required(self):
        self.agent_one_ticket.status = TicketStatus.IN_PROGRESS
        self.agent_one_ticket.save(update_fields=["status"])
        self.authenticate(self.team_user)
        response = self.client.post(
            reverse("ticket-transition", args=[self.agent_one_ticket.id]),
            {"status": TicketStatus.RESOLVED},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("resolution_notes", response.data)

    def test_internal_comments_are_hidden_from_agents(self):
        TicketComment.objects.create(
            ticket=self.agent_one_ticket,
            author=self.team_user,
            body="Internal troubleshooting note.",
            is_internal=True,
        )
        TicketComment.objects.create(
            ticket=self.agent_one_ticket,
            author=self.team_user,
            body="Visible update.",
            is_internal=False,
        )

        self.authenticate(self.agent_one)
        response = self.client.get(
            reverse("ticket-comments", args=[self.agent_one_ticket.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["body"], "Visible update.")

    def test_team_can_create_ticket_on_behalf_of_agent(self):
        self.authenticate(self.team_user)
        response = self.client.post(
            reverse("ticket-list"),
            {
                "reporter_id": self.agent_two.id,
                "title": "Created after walk-up request",
                "description": "Agent could not open the ticketing page.",
                "category": "Network Issue",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        ticket = Ticket.objects.get(pk=response.data["id"])
        self.assertEqual(ticket.reporter, self.agent_two)
        self.assertEqual(ticket.created_by, self.team_user)

    def test_agent_cannot_assign_a_ticket(self):
        self.authenticate(self.agent_one)
        response = self.client.post(
            reverse("ticket-assign", args=[self.agent_one_ticket.id]),
            {"assignee": self.team_user.id},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_invalid_status_transition_is_rejected(self):
        self.authenticate(self.team_user)
        response = self.client.post(
            reverse("ticket-transition", args=[self.agent_one_ticket.id]),
            {
                "status": TicketStatus.RESOLVED,
                "resolution_notes": "Attempted to skip required workflow steps.",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("status", response.data)

    def test_configuration_matches_existing_appscript_values(self):
        self.authenticate(self.agent_one)
        response = self.client.get(reverse("ticket-configuration"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["statuses"],
            [
                "Open",
                "Assigned",
                "In Progress",
                "On Hold",
                "Resolved",
                "Closed",
                "Reopened",
            ],
        )
        self.assertIn("Data Quality Issue", response.data["ticket_types"])
        self.assertIn("Gear01", response.data["workstations"])
        self.assertEqual(response.data["priority_colors"]["Urgent"], "#ef4444")
        self.assertEqual(
            response.data["status_transitions"]["Open"],
            ["Assigned", "In Progress"],
        )

    def test_summary_respects_agent_and_team_permissions(self):
        self.agent_one_ticket.priority = TicketPriority.URGENT
        self.agent_one_ticket.save(update_fields=["priority"])

        self.authenticate(self.agent_one)
        response = self.client.get(reverse("ticket-summary"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total"], 1)
        self.assertEqual(response.data["active"], 1)
        self.assertEqual(response.data["urgent"], 1)

        self.authenticate(self.team_user)
        response = self.client.get(reverse("ticket-summary"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total"], 2)
        self.assertEqual(response.data["unassigned"], 2)

    def test_analytics_and_csv_export_are_team_only(self):
        self.authenticate(self.agent_one)
        response = self.client.get(reverse("ticket-analytics"))
        self.assertEqual(response.status_code, 403)
        response = self.client.get(reverse("ticket-export"))
        self.assertEqual(response.status_code, 403)

        self.agent_one_ticket.title = "=unsafe spreadsheet formula"
        self.agent_one_ticket.save(update_fields=["title"])
        self.authenticate(self.team_user)
        response = self.client.get(reverse("ticket-analytics"), {"period": 30})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["metrics"]["total"], 2)
        self.assertEqual(len(response.data["by_status"]), 1)

        response = self.client.get(reverse("ticket-export"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        content = response.content.decode("utf-8-sig")
        rows = list(csv.reader(io.StringIO(content)))
        self.assertEqual(rows[0][0], "Ticket ID")
        exported_title = next(row[3] for row in rows[1:] if "unsafe" in row[3])
        self.assertTrue(exported_title.startswith("'="))

    @override_settings(
        TICKET_NOTIFICATION_WEBHOOK_URL="https://notifications.example.test/hook"
    )
    def test_public_ticket_events_queue_notifications_but_internal_notes_do_not(self):
        self.authenticate(self.agent_one)
        response = self.client.post(
            reverse("ticket-list"),
            {
                "title": "Notification queue test",
                "description": "Synthetic notification test.",
                "category": "Others",
                "priority": "Moderate",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        ticket = Ticket.objects.get(pk=response.data["id"])
        self.assertTrue(
            TicketNotification.objects.filter(
                ticket=ticket,
                event_type="created",
            ).exists()
        )

        TicketNotification.objects.all().delete()
        self.authenticate(self.team_user)
        response = self.client.post(
            reverse("ticket-comments", args=[ticket.id]),
            {"body": "Private diagnostic detail.", "is_internal": True},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertFalse(TicketNotification.objects.exists())

    def test_imported_ticket_keeps_its_apps_script_id(self):
        self.agent_one_ticket.source_ticket_id = "GRTKT-00123"
        self.agent_one_ticket.save(update_fields=["source_ticket_id"])
        self.authenticate(self.agent_one)
        response = self.client.get(
            reverse("ticket-detail", args=[self.agent_one_ticket.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["ticket_id"], "GRTKT-00123")


class AppScriptImportTests(TestCase):
    def write_csv(self, directory, name, headers, rows):
        file_name = Path(directory) / name
        with file_name.open("w", encoding="utf-8", newline="") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)
        return str(file_name)

    def test_imports_source_ids_roles_ticket_comments_and_history(self):
        with tempfile.TemporaryDirectory() as directory:
            users = self.write_csv(
                directory,
                "Users.csv",
                ["email", "name", "role", "department", "isActive"],
                [
                    {
                        "email": "agent@nvidia.com",
                        "name": "Example Agent",
                        "role": "Agent",
                        "department": "Robotics",
                        "isActive": "TRUE",
                    },
                    {
                        "email": "tech@nvidia.com",
                        "name": "Example Tech",
                        "role": "Tech Team",
                        "department": "Robotics",
                        "isActive": "TRUE",
                    },
                ],
            )
            tickets = self.write_csv(
                directory,
                "Tickets.csv",
                [
                    "ticketId",
                    "createdAt",
                    "updatedAt",
                    "downtimeStart",
                    "downtimeEnd",
                    "downtimeMinutes",
                    "title",
                    "description",
                    "ticketType",
                    "priority",
                    "workstation",
                    "location",
                    "status",
                    "assignedTo",
                    "assignedName",
                    "requesterEmail",
                    "requesterName",
                    "createdByEmail",
                    "createdByName",
                    "resolutionNotes",
                    "resolutionMinutes",
                    "responseMinutes",
                    "escalatedCount",
                    "escalatedTo",
                    "reopenCount",
                    "tags",
                    "rootCause",
                    "impactLevel",
                    "affectedStations",
                ],
                [
                    {
                        "ticketId": "GRTKT-00042",
                        "createdAt": "2026-07-24T09:00:00+08:00",
                        "updatedAt": "2026-07-24T09:15:00+08:00",
                        "downtimeStart": "2026-07-24T09:00:00+08:00",
                        "title": "Fake calibration example",
                        "description": "Synthetic test data only.",
                        "ticketType": "Calibration Issue",
                        "priority": "High",
                        "workstation": "Gear01",
                        "location": "Room A",
                        "status": "Assigned",
                        "assignedTo": "tech@nvidia.com",
                        "assignedName": "Example Tech",
                        "requesterEmail": "agent@nvidia.com",
                        "requesterName": "Example Agent",
                        "createdByEmail": "agent@nvidia.com",
                        "createdByName": "Example Agent",
                        "responseMinutes": "15",
                        "escalatedCount": "0",
                        "reopenCount": "0",
                        "tags": "synthetic",
                        "impactLevel": "Medium",
                        "affectedStations": "Gear01",
                    }
                ],
            )
            comments = self.write_csv(
                directory,
                "Comments.csv",
                [
                    "commentId",
                    "ticketId",
                    "authorEmail",
                    "authorName",
                    "authorRole",
                    "content",
                    "isInternal",
                    "createdAt",
                ],
                [
                    {
                        "commentId": "CMT-00000042",
                        "ticketId": "GRTKT-00042",
                        "authorEmail": "tech@nvidia.com",
                        "authorName": "Example Tech",
                        "authorRole": "Tech Team",
                        "content": "Synthetic troubleshooting note.",
                        "isInternal": "TRUE",
                        "createdAt": "2026-07-24T09:16:00+08:00",
                    }
                ],
            )
            history = self.write_csv(
                directory,
                "StatusHistory.csv",
                [
                    "eventId",
                    "ticketId",
                    "eventType",
                    "fromStatus",
                    "toStatus",
                    "actorEmail",
                    "actorName",
                    "note",
                    "createdAt",
                ],
                [
                    {
                        "eventId": "EVT-0000042",
                        "ticketId": "GRTKT-00042",
                        "eventType": "ASSIGNED",
                        "fromStatus": "Open",
                        "toStatus": "Assigned",
                        "actorEmail": "tech@nvidia.com",
                        "actorName": "Example Tech",
                        "note": "Synthetic assignment.",
                        "createdAt": "2026-07-24T09:15:00+08:00",
                    }
                ],
            )

            call_command(
                "import_appscript_csv",
                users=users,
                tickets=tickets,
                comments=comments,
                history=history,
            )

        ticket = Ticket.objects.get(source_ticket_id="GRTKT-00042")
        self.assertEqual(ticket.priority, TicketPriority.HIGH)
        self.assertEqual(ticket.status, TicketStatus.ASSIGNED)
        self.assertEqual(ticket.assignee.role, UserRole.TEAM)
        self.assertEqual(ticket.comments.get().source_comment_id, "CMT-00000042")
        self.assertEqual(ticket.events.get().source_event_id, "EVT-0000042")


class PilotDataTests(TestCase):
    def test_pilot_seed_requires_explicit_confirmation(self):
        with self.assertRaises(CommandError):
            call_command("seed_pilot_data")

    @patch.dict(
        os.environ,
        {"NVGS_PILOT_PASSWORD": "temporary-pilot-password"},
    )
    def test_pilot_seed_creates_fake_roles_and_marked_tickets(self):
        call_command("seed_pilot_data", confirm=True)

        self.assertEqual(
            User.objects.filter(department="Robotics Pilot").count(),
            5,
        )
        self.assertEqual(
            User.objects.filter(
                department="Robotics Pilot",
                role=UserRole.TEAM,
            ).count(),
            3,
        )
        self.assertEqual(
            Ticket.objects.filter(tags__contains="nvgs-pilot").count(),
            4,
        )


class TicketDashboardTests(TestCase):
    def setUp(self):
        self.password = "a-long-test-password"
        self.agent = User.objects.create_user(
            email="dashboard.agent@nvidia.com",
            password=self.password,
            first_name="Dashboard",
            last_name="Agent",
        )

    def test_dashboard_requires_login(self):
        response = self.client.get("/tickets/")
        self.assertRedirects(
            response,
            "/login/?next=/tickets/",
            fetch_redirect_response=False,
        )

    def test_dashboard_sets_csrf_and_security_headers(self):
        self.client.force_login(self.agent)
        response = self.client.get("/tickets/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Report a production issue")
        self.assertContains(response, "tickets/dashboard.js")
        self.assertIn("csrftoken", response.cookies)
        self.assertEqual(response["Referrer-Policy"], "same-origin")
        self.assertIn("default-src 'self'", response["Content-Security-Policy"])
        self.assertNotIn("'unsafe-inline'", response["Content-Security-Policy"])

    def test_login_page_offers_apps_script_and_local_fallback(self):
        response = self.client.get("/login/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sign in with NVGS password")
        self.assertContains(response, "NVIDIA or Google corporate password")
        self.assertNotContains(response, "Continue with NVIDIA Google")

    def test_browser_style_csrf_ticket_creation(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.agent)
        dashboard = client.get("/tickets/", secure=True)
        csrf_token = dashboard.cookies["csrftoken"].value

        response = client.post(
            "/api/tickets/",
            data={
                "title": "Synthetic browser workflow",
                "description": "Created through the dashboard API contract.",
                "category": "Software Issue",
                "priority": "High",
                "workstation": "Gear05",
            },
            content_type="application/json",
            secure=True,
            HTTP_X_CSRFTOKEN=csrf_token,
            HTTP_ORIGIN="https://testserver",
        )

        self.assertEqual(response.status_code, 201)
        ticket = Ticket.objects.get(title="Synthetic browser workflow")
        self.assertEqual(ticket.reporter, self.agent)
        self.assertEqual(ticket.status, TicketStatus.OPEN)
