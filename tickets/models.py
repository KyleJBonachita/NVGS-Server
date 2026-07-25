from django.conf import settings
from django.db import models
from django.utils import timezone


class TicketStatus(models.TextChoices):
    OPEN = "Open", "Open"
    ASSIGNED = "Assigned", "Assigned"
    IN_PROGRESS = "In Progress", "In Progress"
    ON_HOLD = "On Hold", "On Hold"
    RESOLVED = "Resolved", "Resolved"
    CLOSED = "Closed", "Closed"
    REOPENED = "Reopened", "Reopened"


class TicketPriority(models.TextChoices):
    URGENT = "Urgent", "Urgent"
    HIGH = "High", "High"
    MODERATE = "Moderate", "Moderate"
    LOW = "Low", "Low"


class TicketCategory(models.TextChoices):
    HARDWARE = "Hardware Issue", "Hardware Issue"
    SOFTWARE = "Software Issue", "Software Issue"
    NETWORK = "Network Issue", "Network Issue"
    ENVIRONMENT = "Environment Issue", "Environment Issue"
    CALIBRATION = "Calibration Issue", "Calibration Issue"
    DATA_QUALITY = "Data Quality Issue", "Data Quality Issue"
    OTHER = "Others", "Others"


class TicketImpact(models.TextChoices):
    CRITICAL = "Critical", "Critical"
    HIGH = "High", "High"
    MEDIUM = "Medium", "Medium"
    LOW = "Low", "Low"


class TicketRootCause(models.TextChoices):
    HARDWARE_FAILURE = "Hardware Failure", "Hardware Failure"
    SOFTWARE_BUG = "Software Bug", "Software Bug"
    USER_ERROR = "User Error", "User Error"
    CONFIGURATION = "Configuration", "Configuration"
    NETWORK = "Network", "Network"
    POWER = "Power", "Power"
    ENVIRONMENTAL = "Environmental", "Environmental"
    UNKNOWN = "Unknown", "Unknown"


STATUS_TRANSITIONS = {
    TicketStatus.OPEN: (TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS),
    TicketStatus.ASSIGNED: (TicketStatus.IN_PROGRESS, TicketStatus.OPEN),
    TicketStatus.IN_PROGRESS: (TicketStatus.ON_HOLD, TicketStatus.RESOLVED),
    TicketStatus.ON_HOLD: (TicketStatus.IN_PROGRESS,),
    TicketStatus.RESOLVED: (TicketStatus.CLOSED, TicketStatus.REOPENED),
    TicketStatus.CLOSED: (TicketStatus.REOPENED,),
    TicketStatus.REOPENED: (TicketStatus.IN_PROGRESS, TicketStatus.ASSIGNED),
}

PRIORITY_COLORS = {
    TicketPriority.URGENT: "#ef4444",
    TicketPriority.HIGH: "#f97316",
    TicketPriority.MODERATE: "#eab308",
    TicketPriority.LOW: "#22c55e",
}

IMPACT_COLORS = {
    TicketImpact.CRITICAL: "#ef4444",
    TicketImpact.HIGH: "#f97316",
    TicketImpact.MEDIUM: "#eab308",
    TicketImpact.LOW: "#22c55e",
}

STATUS_COLORS = {
    TicketStatus.OPEN: "#4ade80",
    TicketStatus.ASSIGNED: "#60a5fa",
    TicketStatus.IN_PROGRESS: "#f59e0b",
    TicketStatus.ON_HOLD: "#a78bfa",
    TicketStatus.RESOLVED: "#fbbf24",
    TicketStatus.CLOSED: "#6b7280",
    TicketStatus.REOPENED: "#f87171",
}

WORKSTATIONS = [
    "Gear01",
    "Gear03",
    "Gear05",
    "Gear06",
    "Gear07",
    "Gear10",
    "Gear12",
    "Gear13",
    "Gear14",
    "Gear15",
    "Gear16",
    "Gear17",
    "Gear19",
    "Gear20",
    "TL Station",
]

LOCATIONS = ["Room A", "Room B"]


class Ticket(models.Model):
    source_ticket_id = models.CharField(
        max_length=32,
        unique=True,
        null=True,
        blank=True,
        help_text="Original GRTKT ID when imported from Apps Script.",
    )
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reported_tickets",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_tickets",
    )
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="assigned_tickets",
        null=True,
        blank=True,
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="resolved_tickets",
        null=True,
        blank=True,
    )
    title = models.CharField(max_length=180)
    description = models.TextField()
    category = models.CharField(
        max_length=40,
        choices=TicketCategory.choices,
        default=TicketCategory.OTHER,
        db_index=True,
    )
    priority = models.CharField(
        max_length=16,
        choices=TicketPriority.choices,
        default=TicketPriority.MODERATE,
        db_index=True,
    )
    status = models.CharField(
        max_length=32,
        choices=TicketStatus.choices,
        default=TicketStatus.OPEN,
        db_index=True,
    )
    location = models.CharField(max_length=120, blank=True)
    workstation = models.CharField(max_length=120, blank=True)
    downtime_start = models.DateTimeField(default=timezone.now)
    downtime_end = models.DateTimeField(null=True, blank=True)
    downtime_minutes = models.PositiveIntegerField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)
    resolution_minutes = models.PositiveIntegerField(null=True, blank=True)
    response_minutes = models.PositiveIntegerField(null=True, blank=True)
    escalated_count = models.PositiveIntegerField(default=0)
    escalated_to = models.CharField(max_length=180, blank=True)
    reopen_count = models.PositiveIntegerField(default=0)
    tags = models.TextField(blank=True)
    root_cause = models.CharField(
        max_length=32,
        choices=TicketRootCause.choices,
        blank=True,
    )
    impact_level = models.CharField(
        max_length=16,
        choices=TicketImpact.choices,
        blank=True,
    )
    affected_stations = models.TextField(blank=True)
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
        if self.source_ticket_id:
            return self.source_ticket_id
        if not self.pk:
            return "NVGS-PENDING"
        created = self.created_at or timezone.now()
        return f"NVGS-{created.year}-{self.pk:06d}"

    def __str__(self):
        return f"{self.reference}: {self.title}"


class TicketComment(models.Model):
    source_comment_id = models.CharField(
        max_length=32,
        unique=True,
        null=True,
        blank=True,
    )
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
    source_event_id = models.CharField(
        max_length=32,
        unique=True,
        null=True,
        blank=True,
    )
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
    from_status = models.CharField(max_length=32, blank=True)
    to_status = models.CharField(max_length=32, blank=True)
    note = models.TextField(blank=True)
    changes = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.ticket.reference}: {self.action}"
