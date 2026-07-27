import os

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import User, UserRole
from tickets.models import (
    Ticket,
    TicketCategory,
    TicketEvent,
    TicketImpact,
    TicketPriority,
    TicketRootCause,
    TicketStatus,
)

PILOT_USERS = [
    (
        "nvgs.pilot.agent.one@nvidia.com",
        "Pilot",
        "Agent One",
        UserRole.AGENT,
    ),
    (
        "nvgs.pilot.agent.two@nvidia.com",
        "Pilot",
        "Agent Two",
        UserRole.AGENT,
    ),
    (
        "nvgs.pilot.tech@nvidia.com",
        "Pilot",
        "Tech Team",
        UserRole.TEAM,
    ),
    (
        "nvgs.pilot.tl@nvidia.com",
        "Pilot",
        "TL",
        UserRole.TEAM,
    ),
    (
        "nvgs.pilot.manager@nvidia.com",
        "Pilot",
        "Manager",
        UserRole.TEAM,
    ),
]


class Command(BaseCommand):
    help = "Create clearly marked fake users and tickets for the browser pilot."

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Confirm that this is a non-production-data pilot.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if not options["confirm"]:
            raise CommandError(
                "Nothing changed. Re-run with --confirm after checking that "
                "only synthetic pilot data will be created."
            )
        password = os.getenv("NVGS_PILOT_PASSWORD", "")
        if len(password) < 12:
            raise CommandError(
                "Set NVGS_PILOT_PASSWORD to a temporary value with at least "
                "12 characters. Do not use a corporate password."
            )

        users = {}
        for email, first_name, last_name, role in PILOT_USERS:
            user, _created = User.objects.get_or_create(
                email=email,
                defaults={
                    "first_name": first_name,
                    "last_name": last_name,
                    "role": role,
                    "department": "Robotics Pilot",
                },
            )
            user.first_name = first_name
            user.last_name = last_name
            user.role = role
            user.department = "Robotics Pilot"
            user.is_active = True
            user.set_password(password)
            user.full_clean()
            user.save()
            users[email] = user

        now = timezone.now()
        examples = [
            {
                "source_ticket_id": "PILOT-00001",
                "reporter": users["nvgs.pilot.agent.one@nvidia.com"],
                "created_by": users["nvgs.pilot.agent.one@nvidia.com"],
                "title": "[PILOT] Camera feed frozen on Gear05",
                "description": "Synthetic ticket for the NVGS browser pilot.",
                "category": TicketCategory.HARDWARE,
                "priority": TicketPriority.URGENT,
                "status": TicketStatus.OPEN,
                "workstation": "Gear05",
                "location": "Room A",
                "impact_level": TicketImpact.HIGH,
                "tags": "nvgs-pilot,synthetic",
            },
            {
                "source_ticket_id": "PILOT-00002",
                "reporter": users["nvgs.pilot.agent.two@nvidia.com"],
                "created_by": users["nvgs.pilot.agent.two@nvidia.com"],
                "assignee": users["nvgs.pilot.tech@nvidia.com"],
                "title": "[PILOT] Robotics tool cannot reach local service",
                "description": "Synthetic assigned ticket for permission testing.",
                "category": TicketCategory.NETWORK,
                "priority": TicketPriority.HIGH,
                "status": TicketStatus.ASSIGNED,
                "workstation": "Gear10",
                "location": "Room B",
                "impact_level": TicketImpact.MEDIUM,
                "tags": "nvgs-pilot,synthetic",
            },
            {
                "source_ticket_id": "PILOT-00003",
                "reporter": users["nvgs.pilot.agent.one@nvidia.com"],
                "created_by": users["nvgs.pilot.agent.one@nvidia.com"],
                "assignee": users["nvgs.pilot.tl@nvidia.com"],
                "title": "[PILOT] Annotation quality check requires review",
                "description": "Synthetic in-progress ticket for workflow testing.",
                "category": TicketCategory.DATA_QUALITY,
                "priority": TicketPriority.MODERATE,
                "status": TicketStatus.IN_PROGRESS,
                "workstation": "Gear01",
                "location": "Room A",
                "impact_level": TicketImpact.LOW,
                "tags": "nvgs-pilot,synthetic",
            },
            {
                "source_ticket_id": "PILOT-00004",
                "reporter": users["nvgs.pilot.agent.two@nvidia.com"],
                "created_by": users["nvgs.pilot.agent.two@nvidia.com"],
                "assignee": users["nvgs.pilot.manager@nvidia.com"],
                "resolved_by": users["nvgs.pilot.manager@nvidia.com"],
                "title": "[PILOT] Application configuration corrected",
                "description": "Synthetic resolved ticket for history testing.",
                "category": TicketCategory.SOFTWARE,
                "priority": TicketPriority.LOW,
                "status": TicketStatus.RESOLVED,
                "workstation": "TL Station",
                "location": "Room A",
                "impact_level": TicketImpact.LOW,
                "root_cause": TicketRootCause.CONFIGURATION,
                "resolution_notes": "Synthetic resolution: corrected a test setting.",
                "resolved_at": now,
                "downtime_end": now,
                "tags": "nvgs-pilot,synthetic",
            },
        ]

        for data in examples:
            source_ticket_id = data.pop("source_ticket_id")
            ticket, created = Ticket.objects.update_or_create(
                source_ticket_id=source_ticket_id,
                defaults=data,
            )
            if created:
                TicketEvent.objects.create(
                    ticket=ticket,
                    actor=ticket.created_by,
                    action="pilot_seeded",
                    from_status="",
                    to_status=ticket.status,
                    note="Synthetic pilot ticket created.",
                    changes={"synthetic": True},
                )

        self.stdout.write(
            self.style.SUCCESS(
                "Pilot data ready: 5 fake users and 4 clearly marked fake tickets."
            )
        )
        self.stdout.write("Use local NVGS login; these are not real Google accounts.")
        for email, *_rest in PILOT_USERS:
            self.stdout.write(f"  {email}")
