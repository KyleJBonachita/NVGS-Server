import csv
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from accounts.models import User, UserRole
from tickets.models import (
    Ticket,
    TicketCategory,
    TicketComment,
    TicketEvent,
    TicketImpact,
    TicketPriority,
    TicketRootCause,
    TicketStatus,
)

ROLE_MAP = {
    "Agent": UserRole.AGENT,
    "Tech Team": UserRole.TEAM,
    "Management": UserRole.TEAM,
}


def read_rows(file_name):
    path = Path(file_name)
    if not path.is_file():
        raise CommandError(f"CSV file does not exist: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
        yield from csv.DictReader(csv_file)


def clean(value):
    return str(value or "").strip()


def integer_or_none(value):
    value = clean(value)
    if not value:
        return None
    try:
        return max(0, int(float(value)))
    except ValueError as error:
        raise CommandError(f"Expected a number but received: {value}") from error


def boolean(value, default=True):
    value = clean(value).lower()
    if not value:
        return default
    return value not in {"false", "0", "no", "inactive"}


def date_or_none(value):
    value = clean(value)
    if not value:
        return None
    parsed = parse_datetime(value)
    if parsed is None:
        raise CommandError(f"Expected an ISO date/time but received: {value}")
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed)
    return parsed


class Command(BaseCommand):
    help = "Import Apps Script Users, Tickets, Comments, and StatusHistory CSVs."

    def add_arguments(self, parser):
        parser.add_argument("--users", help="Users sheet exported as CSV.")
        parser.add_argument("--tickets", help="Tickets sheet exported as CSV.")
        parser.add_argument("--comments", help="Comments sheet exported as CSV.")
        parser.add_argument("--history", help="StatusHistory sheet exported as CSV.")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate and count rows, then roll back all database changes.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if not any(
            options.get(name) for name in ("users", "tickets", "comments", "history")
        ):
            raise CommandError("Provide at least one CSV file.")

        counts = {"users": 0, "tickets": 0, "comments": 0, "history": 0}
        if options.get("users"):
            counts["users"] = self.import_users(options["users"])
        if options.get("tickets"):
            counts["tickets"] = self.import_tickets(options["tickets"])
        if options.get("comments"):
            counts["comments"] = self.import_comments(options["comments"])
        if options.get("history"):
            counts["history"] = self.import_history(options["history"])

        if options["dry_run"]:
            transaction.set_rollback(True)

        mode = "validated (nothing saved)" if options["dry_run"] else "imported"
        self.stdout.write(
            self.style.SUCCESS(
                f"{mode}: {counts['users']} users, {counts['tickets']} tickets, "
                f"{counts['comments']} comments, {counts['history']} history events."
            )
        )

    def allowed_email(self, value):
        email = User.objects.normalize_email(clean(value)).lower()
        domain = email.rsplit("@", 1)[-1] if "@" in email else ""
        if not email or (
            settings.ALLOWED_EMAIL_DOMAINS
            and domain not in settings.ALLOWED_EMAIL_DOMAINS
        ):
            raise CommandError("CSV contains an email outside the approved domains.")
        return email

    def get_user(self, email_value, name="", role=None):
        email = self.allowed_email(email_value)
        initial_role = role or UserRole.AGENT
        user, created = User.objects.get_or_create(
            email=email,
            defaults={"role": initial_role},
        )
        changed = []
        if created:
            user.set_unusable_password()
            changed.append("password")
        if (
            role is not None
            and user.role != UserRole.SYSTEM_ADMIN
            and user.role != role
        ):
            user.role = role
            changed.append("role")
        name = clean(name)
        if name:
            first_name, _, last_name = name.partition(" ")
            if user.first_name != first_name:
                user.first_name = first_name
                changed.append("first_name")
            if user.last_name != last_name:
                user.last_name = last_name
                changed.append("last_name")
        if changed:
            user.save(update_fields=[*set(changed)])
        return user

    def import_users(self, file_name):
        count = 0
        for row in read_rows(file_name):
            role = ROLE_MAP.get(clean(row.get("role")), UserRole.AGENT)
            user = self.get_user(row.get("email"), row.get("name"), role)
            user.department = clean(row.get("department"))
            user.is_active = boolean(row.get("isActive"))
            user.save(update_fields=["department", "is_active"])
            count += 1
        return count

    def choice(self, value, allowed, default, field_name):
        value = clean(value)
        if not value:
            return default
        if value not in allowed:
            raise CommandError(f"Unknown {field_name}: {value}")
        return value

    def import_tickets(self, file_name):
        count = 0
        for row in read_rows(file_name):
            source_id = clean(row.get("ticketId"))
            if not source_id:
                raise CommandError("A Tickets row is missing ticketId.")

            reporter = self.get_user(
                row.get("requesterEmail"),
                row.get("requesterName"),
            )
            creator = self.get_user(
                row.get("createdByEmail") or row.get("requesterEmail"),
                row.get("createdByName") or row.get("requesterName"),
            )
            assignee = None
            if clean(row.get("assignedTo")):
                assignee = self.get_user(
                    row.get("assignedTo"),
                    row.get("assignedName"),
                    UserRole.TEAM,
                )
            resolver = None
            if clean(row.get("resolvedByEmail")):
                resolver = self.get_user(
                    row.get("resolvedByEmail"),
                    row.get("resolvedByName"),
                    UserRole.TEAM,
                )

            created_at = date_or_none(row.get("createdAt")) or timezone.now()
            updated_at = date_or_none(row.get("updatedAt")) or created_at
            downtime_start = (
                date_or_none(row.get("downtimeStart")) or created_at
            )
            downtime_end = date_or_none(row.get("downtimeEnd"))
            status = self.choice(
                row.get("status"),
                TicketStatus.values,
                TicketStatus.OPEN,
                "status",
            )
            defaults = {
                "reporter": reporter,
                "created_by": creator,
                "assignee": assignee,
                "resolved_by": resolver,
                "title": clean(row.get("title")),
                "description": clean(row.get("description")),
                "category": self.choice(
                    row.get("ticketType"),
                    TicketCategory.values,
                    TicketCategory.OTHER,
                    "ticket type",
                ),
                "priority": self.choice(
                    row.get("priority"),
                    TicketPriority.values,
                    TicketPriority.MODERATE,
                    "priority",
                ),
                "status": status,
                "workstation": clean(row.get("workstation")),
                "location": clean(row.get("location")),
                "downtime_start": downtime_start,
                "downtime_end": downtime_end,
                "downtime_minutes": integer_or_none(row.get("downtimeMinutes")),
                "resolution_notes": clean(row.get("resolutionNotes")),
                "resolution_minutes": integer_or_none(
                    row.get("resolutionMinutes")
                ),
                "response_minutes": integer_or_none(row.get("responseMinutes")),
                "escalated_count": integer_or_none(row.get("escalatedCount")) or 0,
                "escalated_to": clean(row.get("escalatedTo")),
                "reopen_count": integer_or_none(row.get("reopenCount")) or 0,
                "tags": clean(row.get("tags")),
                "root_cause": self.choice(
                    row.get("rootCause"),
                    TicketRootCause.values,
                    "",
                    "root cause",
                ),
                "impact_level": self.choice(
                    row.get("impactLevel"),
                    TicketImpact.values,
                    "",
                    "impact level",
                ),
                "affected_stations": clean(row.get("affectedStations")),
                "resolved_at": downtime_end
                if status in {TicketStatus.RESOLVED, TicketStatus.CLOSED}
                else None,
            }
            ticket, _ = Ticket.objects.update_or_create(
                source_ticket_id=source_id,
                defaults=defaults,
            )
            Ticket.objects.filter(pk=ticket.pk).update(
                created_at=created_at,
                updated_at=updated_at,
            )
            count += 1
        return count

    def import_comments(self, file_name):
        count = 0
        for row in read_rows(file_name):
            source_id = clean(row.get("commentId"))
            ticket_id = clean(row.get("ticketId"))
            if not source_id or not ticket_id:
                raise CommandError("A Comments row is missing commentId or ticketId.")
            try:
                ticket = Ticket.objects.get(source_ticket_id=ticket_id)
            except Ticket.DoesNotExist as error:
                raise CommandError(
                    f"Comment refers to a missing ticket: {ticket_id}"
                ) from error
            author = self.get_user(
                row.get("authorEmail"),
                row.get("authorName"),
                ROLE_MAP.get(clean(row.get("authorRole")), UserRole.AGENT),
            )
            created_at = date_or_none(row.get("createdAt")) or timezone.now()
            comment, _ = TicketComment.objects.update_or_create(
                source_comment_id=source_id,
                defaults={
                    "ticket": ticket,
                    "author": author,
                    "body": clean(row.get("content")),
                    "is_internal": boolean(row.get("isInternal"), default=False),
                },
            )
            TicketComment.objects.filter(pk=comment.pk).update(
                created_at=created_at
            )
            count += 1
        return count

    def import_history(self, file_name):
        count = 0
        for row in read_rows(file_name):
            source_id = clean(row.get("eventId"))
            ticket_id = clean(row.get("ticketId"))
            if not source_id or not ticket_id:
                raise CommandError(
                    "A StatusHistory row is missing eventId or ticketId."
                )
            try:
                ticket = Ticket.objects.get(source_ticket_id=ticket_id)
            except Ticket.DoesNotExist as error:
                raise CommandError(
                    f"History refers to a missing ticket: {ticket_id}"
                ) from error
            actor = self.get_user(
                row.get("actorEmail"),
                row.get("actorName"),
            )
            created_at = date_or_none(row.get("createdAt")) or timezone.now()
            event, _ = TicketEvent.objects.update_or_create(
                source_event_id=source_id,
                defaults={
                    "ticket": ticket,
                    "actor": actor,
                    "action": clean(row.get("eventType")) or "imported",
                    "from_status": clean(row.get("fromStatus")),
                    "to_status": clean(row.get("toStatus")),
                    "note": clean(row.get("note")),
                    "changes": {},
                },
            )
            TicketEvent.objects.filter(pk=event.pk).update(created_at=created_at)
            count += 1
        return count
