from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.models import User, UserRole
from .models import (
    Ticket,
    TicketComment,
    TicketEvent,
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
            title="Robot console issue",
            description="The console does not load.",
        )
        self.agent_two_ticket = Ticket.objects.create(
            reporter=self.agent_two,
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

    def test_agent_created_ticket_cannot_self_assign_or_set_priority(self):
        self.authenticate(self.agent_one)
        response = self.client.post(
            reverse("ticket-list"),
            {
                "title": "Application error",
                "description": "The robotics application displays an error.",
                "category": "robotics",
                "priority": TicketPriority.URGENT,
                "status": TicketStatus.RESOLVED,
                "resolution": "Untrusted client-provided resolution",
                "assignee": 999999,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        ticket = Ticket.objects.get(pk=response.data["id"])
        self.assertEqual(ticket.reporter, self.agent_one)
        self.assertEqual(ticket.priority, TicketPriority.NORMAL)
        self.assertEqual(ticket.status, TicketStatus.NEW)
        self.assertIsNone(ticket.assignee)
        self.assertEqual(ticket.resolution, "")
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
            {"status": TicketStatus.CLOSED, "resolution": "Done"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_team_can_see_and_manage_all_tickets(self):
        self.authenticate(self.team_user)
        response = self.client.get(reverse("ticket-list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)

        response = self.client.patch(
            reverse("ticket-detail", args=[self.agent_one_ticket.id]),
            {
                "assignee": self.team_user.id,
                "status": TicketStatus.RESOLVED,
                "resolution": "Restarted the robotics console service.",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.agent_one_ticket.refresh_from_db()
        self.assertEqual(self.agent_one_ticket.assignee, self.team_user)
        self.assertEqual(self.agent_one_ticket.status, TicketStatus.RESOLVED)
        self.assertIsNotNone(self.agent_one_ticket.resolved_at)
        self.assertTrue(
            TicketEvent.objects.filter(
                ticket=self.agent_one_ticket,
                action="updated",
            ).exists()
        )

    def test_resolution_is_required(self):
        self.authenticate(self.team_user)
        response = self.client.patch(
            reverse("ticket-detail", args=[self.agent_one_ticket.id]),
            {"status": TicketStatus.RESOLVED},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("resolution", response.data)

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
                "category": "network",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        ticket = Ticket.objects.get(pk=response.data["id"])
        self.assertEqual(ticket.reporter, self.agent_two)
