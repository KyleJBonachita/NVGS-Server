from django.conf import settings
from django.db import models
from django.utils import timezone


class TicketStatus(models.TextChoices):
    NEW = "new", "New"
    ACKNOWLEDGED = "acknowledged", "Acknowledged"
    ASSIGNED = "assigned", "Assigned"
    IN_PROGRESS = "in_progress", "In progress"
    WAITING_FOR_AGENT = "waiting_for_agent", "Waiting for agent"
    RESOLVED = "resolved", "Resolved"
    CLOSED = "closed", "Closed"
    CANCELLED = "cancelled", "Cancelled"


class TicketPriority(models.TextChoices):
    LOW = "low", "Low"
    NORMAL = "normal", "Normal"
    HIGH = "high", "High"
    URGENT = "urgent", "Urgent"


class TicketCategory(models.TextChoices):
    HARDWARE = "hardware", "Hardware"
    SOFTWARE = "software", "Software"
    NETWORK = "network", "Network"
    ACCESS = "access", "Account or access"
    ROBOTICS = "robotics", "Robotics"
    OTHER = "other", "Other"


class Ticket(models.Model):
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reported_tickets",
    )
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="assigned_tickets",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=180)
    description = models.TextField()
    category = models.CharField(
        max_length=32,
        choices=TicketCategory.choices,
        default=TicketCategory.OTHER,
        db_index=True,
    )
    priority = models.CharField(
        max_length=16,
        choices=TicketPriority.choices,
        default=TicketPriority.NORMAL,
        db_index=True,
    )
    status = models.CharField(
        max_length=32,
        choices=TicketStatus.choices,
        default=TicketStatus.NEW,
        db_index=True,
    )
    area = models.CharField(max_length=120, blank=True)
    workstation = models.CharField(max_length=120, blank=True)
    resolution = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["assignee", "status"]),
            models.Index(fields=["reporter", "-created_at"]),
        ]

    @property
    def reference(self) -> str:
        if not self.pk:
            return "NVGS-PENDING"
        created = self.created_at or timezone.now()
        return f"NVGS-{created.year}-{self.pk:06d}"

    def __str__(self):
        return f"{self.reference}: {self.title}"


class TicketComment(models.Model):
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="ticket_comments",
    )
    body = models.TextField()
    is_internal = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Comment on {self.ticket.reference} by {self.author}"


class TicketEvent(models.Model):
    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="events",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="ticket_events",
    )
    action = models.CharField(max_length=64)
    changes = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.ticket.reference}: {self.action}"

