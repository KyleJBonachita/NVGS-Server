from __future__ import annotations

import json
import urllib.request
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import Ticket, TicketNotification

NOTIFIABLE_EVENTS = {
    "created",
    "assigned",
    "status_changed",
    "escalated",
    "comment_added",
}


def queue_ticket_notification(
    *,
    ticket: Ticket,
    event_type: str,
    actor_name: str,
    note: str = "",
) -> TicketNotification | None:
    if (
        not settings.TICKET_NOTIFICATION_WEBHOOK_URL
        or event_type not in NOTIFIABLE_EVENTS
    ):
        return None

    reporter = ticket.reporter.display_name
    assignee = ticket.assignee.display_name if ticket.assignee else "Unassigned"
    return TicketNotification.objects.create(
        ticket=ticket,
        event_type=event_type,
        payload={
            "ticket_id": ticket.pk,
            "reference": ticket.reference,
            "title": ticket.title,
            "status": ticket.status,
            "priority": ticket.priority,
            "reporter": reporter,
            "assignee": assignee,
            "actor": actor_name,
            "note": note[:2000],
            "ticket_path": f"/tickets/?ticket={ticket.pk}",
        },
    )


def deliver_notification(notification: TicketNotification) -> None:
    payload = notification.payload
    event_label = notification.event_type.replace("_", " ").title()
    message = (
        f"[NVGS] {event_label}: {payload['reference']} - {payload['title']} "
        f"| {payload['priority']} | {payload['status']} "
        f"| Reporter: {payload['reporter']} | Assignee: {payload['assignee']}"
    )
    if payload.get("note"):
        message += f" | Note: {payload['note']}"

    body = json.dumps(
        {
            "text": message,
            "source": "NVGS Ticketing",
            "event": notification.event_type,
            "ticket": payload,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        settings.TICKET_NOTIFICATION_WEBHOOK_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "NVGS-Ticketing/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(
        request,
        timeout=settings.TICKET_NOTIFICATION_TIMEOUT_SECONDS,
    ) as response:
        if not 200 <= response.status < 300:
            raise RuntimeError(f"Webhook returned HTTP {response.status}.")


def record_delivery_failure(
    notification: TicketNotification,
    error: Exception,
) -> None:
    notification.attempts += 1
    delay_minutes = min(60, 2 ** min(notification.attempts, 6))
    notification.next_attempt_at = timezone.now() + timedelta(
        minutes=delay_minutes
    )
    notification.last_error = f"{type(error).__name__}: {error}"[:240]
    notification.save(
        update_fields=[
            "attempts",
            "next_attempt_at",
            "last_error",
        ]
    )
