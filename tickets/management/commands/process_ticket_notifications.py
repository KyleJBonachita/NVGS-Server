import time

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from tickets.models import TicketNotification
from tickets.notifications import (
    deliver_notification,
    notification_configuration,
    record_delivery_failure,
)


class Command(BaseCommand):
    help = "Send queued ticket notifications without blocking ticket requests."

    def add_arguments(self, parser):
        parser.add_argument(
            "--once",
            action="store_true",
            help="Process the current queue once, then stop.",
        )

    def handle(self, *args, **options):
        once = options["once"]
        mode, configured = notification_configuration()
        if not configured:
            if once:
                self.stdout.write(
                    f"Ticket notification delivery is not configured (mode: {mode})."
                )
                return
            self.stdout.write(
                f"Ticket notification delivery is not configured (mode: {mode}); "
                "waiting for configuration."
            )

        while True:
            processed = self.process_batch()
            if once:
                return
            time.sleep(2 if processed else 10)

    def process_batch(self) -> int:
        _mode, configured = notification_configuration()
        if not configured:
            return 0

        notifications = list(
            TicketNotification.objects.filter(
                sent_at__isnull=True,
                attempts__lt=settings.TICKET_NOTIFICATION_MAX_ATTEMPTS,
                next_attempt_at__lte=timezone.now(),
            )
            .select_related("ticket")
            .order_by("created_at")[:25]
        )
        for notification in notifications:
            try:
                deliver_notification(notification)
            except Exception as exc:
                record_delivery_failure(notification, exc)
                self.stderr.write(
                    f"Notification {notification.pk} failed: "
                    f"{type(exc).__name__}"
                )
                continue

            notification.sent_at = timezone.now()
            notification.attempts += 1
            notification.last_error = ""
            notification.save(
                update_fields=["sent_at", "attempts", "last_error"]
            )
            self.stdout.write(f"Sent notification {notification.pk}.")
        return len(notifications)
