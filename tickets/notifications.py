from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
import urllib.request
from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMessage
from django.utils import timezone

from .models import Ticket, TicketNotification

NOTIFIABLE_EVENTS = {
    "created",
    "assigned",
    "status_changed",
    "resolved",
    "reopened",
    "escalated",
    "comment_added",
}

POWER_AUTOMATE_EVENTS = {
    "created": ("TICKET_CREATED", "Ticket created"),
    "assigned": ("TICKET_ASSIGNED", "Ticket assigned"),
    "status_changed": ("TICKET_STATUS_CHANGED", "Ticket status changed"),
    "resolved": ("TICKET_RESOLVED", "Ticket resolved"),
    "reopened": ("TICKET_REOPENED", "Ticket reopened"),
    "escalated": ("TICKET_ESCALATED", "Ticket escalated"),
    "comment_added": ("TICKET_COMMENT_ADDED", "Ticket comment added"),
}


def notification_configuration() -> tuple[str, bool]:
    mode = settings.TICKET_NOTIFICATION_DELIVERY_MODE
    if mode == "webhook":
        return mode, bool(settings.TICKET_NOTIFICATION_WEBHOOK_URL)
    if mode == "email":
        smtp_ready = (
            settings.EMAIL_BACKEND
            != "django.core.mail.backends.smtp.EmailBackend"
            or bool(settings.EMAIL_HOST)
        )
        return mode, bool(
            smtp_ready
            and settings.TICKET_NOTIFICATION_EMAIL_TO
            and settings.DEFAULT_FROM_EMAIL
        )
    if mode == "appscript":
        return mode, bool(
            settings.TICKET_NOTIFICATION_APPSCRIPT_URL
            and len(settings.TICKET_NOTIFICATION_APPSCRIPT_SECRET) >= 32
        )
    return "disabled", False


def queue_ticket_notification(
    *,
    ticket: Ticket,
    event_type: str,
    actor_name: str,
    actor_email: str = "",
    actor_role: str = "",
    note: str = "",
) -> TicketNotification | None:
    _mode, configured = notification_configuration()
    if not configured or event_type not in NOTIFIABLE_EVENTS:
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
            "actor_email": actor_email,
            "actor_role": actor_role,
            "note": note[:2000],
            "ticket_path": f"/tickets/?ticket={ticket.pk}",
            "created_at": ticket.created_at.isoformat(),
            "updated_at": ticket.updated_at.isoformat(),
            "description": ticket.description,
            "category": ticket.category,
            "workstation": ticket.workstation,
            "location": ticket.location,
            "reporter_email": ticket.reporter.email,
            "assignee_email": ticket.assignee.email if ticket.assignee else "",
            "impact_level": ticket.impact_level,
            "downtime_start": (
                ticket.downtime_start.isoformat() if ticket.downtime_start else ""
            ),
            "downtime_end": (
                ticket.downtime_end.isoformat() if ticket.downtime_end else ""
            ),
            "downtime_minutes": ticket.downtime_minutes,
        },
    )


def _message_text(notification: TicketNotification) -> str:
    payload = notification.payload
    event_label = notification.event_type.replace("_", " ").title()
    message = (
        f"[NVGS] {event_label}: {payload['reference']} - {payload['title']} "
        f"| {payload['priority']} | {payload['status']} "
        f"| Reporter: {payload['reporter']} | Assignee: {payload['assignee']}"
    )
    if payload.get("note"):
        message += f" | Note: {payload['note']}"
    return message


def _power_automate_payload(notification: TicketNotification) -> dict:
    payload = notification.payload
    event_type, event_case = POWER_AUTOMATE_EVENTS[notification.event_type]
    base_url = settings.TICKET_NOTIFICATION_PUBLIC_BASE_URL
    ticket_path = payload["ticket_path"]
    ticket_url = f"{base_url}{ticket_path}" if base_url else ticket_path
    return {
        "app": "GRTKT",
        "eventType": event_type,
        "eventCase": event_case,
        "deliveryOption": "EMAIL_FLOW",
        "ticketUrl": ticket_url,
        "ticket": {
            "ticketId": payload["reference"],
            "title": payload["title"],
            "description": payload.get("description", ""),
            "status": payload["status"],
            "priority": payload["priority"],
            "ticketType": payload.get("category", ""),
            "workstation": payload.get("workstation", ""),
            "location": payload.get("location", ""),
            "requesterName": payload["reporter"],
            "requesterEmail": payload.get("reporter_email", ""),
            "assignedName": payload["assignee"],
            "assignedTo": payload.get("assignee_email", ""),
            "impactLevel": payload.get("impact_level", ""),
            "updatedAt": payload.get("updated_at", ""),
            "downtimeStart": payload.get("downtime_start", ""),
            "downtimeEnd": payload.get("downtime_end", ""),
            "downtimeMinutes": payload.get("downtime_minutes"),
        },
        "actor": {
            "email": payload.get("actor_email", ""),
            "name": payload["actor"],
            "role": payload.get("actor_role", ""),
        },
        "note": payload.get("note", ""),
        "teams": {
            "targetType": "groupChat",
            "targetName": settings.TICKET_NOTIFICATION_EMAIL_TARGET_NAME,
            "groupChatId": settings.TICKET_NOTIFICATION_TEAMS_CHAT_ID,
            "mentions": [],
        },
        "actions": [],
        "actionExpiresAt": "",
        "idempotencyKey": f"nvgs-ticket-notification-{notification.pk}",
        "sentAt": timezone.now().isoformat(),
    }


def _deliver_webhook(notification: TicketNotification) -> None:
    payload = notification.payload
    message = _message_text(notification)

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


def _deliver_email(notification: TicketNotification) -> None:
    event_type, _event_case = POWER_AUTOMATE_EVENTS[notification.event_type]
    payload = notification.payload
    message = EmailMessage(
        subject=f"GRTKT_EVENT {event_type} {payload['reference']}",
        body=json.dumps(
            _power_automate_payload(notification),
            ensure_ascii=False,
            indent=2,
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=settings.TICKET_NOTIFICATION_EMAIL_TO,
    )
    sent_count = message.send(fail_silently=False)
    if sent_count != 1:
        raise RuntimeError("Email backend did not confirm delivery.")


def _deliver_appscript(notification: TicketNotification) -> None:
    payload_json = json.dumps(
        _power_automate_payload(notification),
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    encoded_payload = base64.urlsafe_b64encode(payload_json).decode("ascii")
    timestamp = int(time.time() * 1000)
    nonce = secrets.token_hex(16)
    signing_input = f"{timestamp}.{nonce}.{encoded_payload}"
    signature = hmac.new(
        settings.TICKET_NOTIFICATION_APPSCRIPT_SECRET.encode("utf-8"),
        signing_input.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    body = json.dumps(
        {
            "version": 1,
            "timestamp": timestamp,
            "nonce": nonce,
            "payload": encoded_payload,
            "signature": signature,
        },
        separators=(",", ":"),
    ).encode("utf-8")
    request = urllib.request.Request(
        settings.TICKET_NOTIFICATION_APPSCRIPT_URL,
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
            raise RuntimeError(
                f"Apps Script bridge returned HTTP {response.status}."
            )
        result = json.loads(response.read(32769).decode("utf-8"))
    if not isinstance(result, dict) or result.get("ok") is not True:
        error_message = (
            result.get("error", "Notification bridge rejected the request.")
            if isinstance(result, dict)
            else "Notification bridge returned an invalid response."
        )
        raise RuntimeError(str(error_message)[:180])


def deliver_notification(notification: TicketNotification) -> None:
    mode, configured = notification_configuration()
    if not configured:
        raise RuntimeError(f"Ticket notification delivery mode {mode!r} is not ready.")
    if mode == "webhook":
        _deliver_webhook(notification)
        return
    if mode == "email":
        _deliver_email(notification)
        return
    if mode == "appscript":
        _deliver_appscript(notification)
        return
    raise RuntimeError("Ticket notifications are disabled.")


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
