import csv
from datetime import timedelta

from django.db.models import Avg, Count, Q
from django.db.models.functions import TruncDate
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from accounts.models import User, UserRole

from .models import (
    IMPACT_COLORS,
    LOCATIONS,
    PRIORITY_COLORS,
    STATUS_COLORS,
    STATUS_TRANSITIONS,
    WORKSTATIONS,
    Ticket,
    TicketCategory,
    TicketEvent,
    TicketImpact,
    TicketPriority,
    TicketRootCause,
    TicketStatus,
)
from .notifications import queue_ticket_notification
from .permissions import CanManageTickets
from .serializers import (
    TicketCommentSerializer,
    TicketEventSerializer,
    TicketSerializer,
)


class TicketViewSet(ModelViewSet):
    serializer_class = TicketSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "patch", "put", "head", "options"]

    tracked_fields = [
        "assignee_id",
        "title",
        "description",
        "category",
        "priority",
        "status",
        "location",
        "workstation",
        "downtime_start",
        "downtime_end",
        "resolution_notes",
        "escalated_to",
        "tags",
        "root_cause",
        "impact_level",
        "affected_stations",
    ]

    def get_permissions(self):
        manager_actions = {
            "update",
            "partial_update",
            "assign",
            "assign_to_me",
            "transition",
            "escalate",
            "bulk_status",
            "analytics",
            "export",
        }
        if self.action in manager_actions:
            return [CanManageTickets()]
        return [IsAuthenticated()]

    def get_queryset(self):
        queryset = (
            Ticket.objects.select_related("reporter", "assignee")
            .annotate(comment_count=Count("comments"))
            .order_by("-created_at")
            .all()
        )
        user = self.request.user
        if not user.is_authenticated:
            return queryset.none()
        if not user.can_manage_tickets:
            queryset = queryset.filter(Q(reporter=user) | Q(created_by=user))

        status_value = self.request.query_params.get("status")
        priority = self.request.query_params.get("priority")
        category = self.request.query_params.get("category")
        workstation = self.request.query_params.get("workstation")
        impact_level = self.request.query_params.get("impact_level")
        assignee = self.request.query_params.get("assignee")
        reporter = self.request.query_params.get("reporter")
        created_after = self.request.query_params.get("created_after")
        created_before = self.request.query_params.get("created_before")
        query = self.request.query_params.get("q")

        if status_value:
            queryset = queryset.filter(status=status_value)
        if priority:
            queryset = queryset.filter(priority=priority)
        if category:
            queryset = queryset.filter(category=category)
        if workstation:
            queryset = queryset.filter(workstation=workstation)
        if impact_level:
            queryset = queryset.filter(impact_level=impact_level)
        if assignee and user.can_manage_tickets:
            queryset = queryset.filter(assignee_id=assignee)
        if reporter and user.can_manage_tickets:
            queryset = queryset.filter(reporter_id=reporter)
        if created_after:
            queryset = queryset.filter(created_at__date__gte=created_after)
        if created_before:
            queryset = queryset.filter(created_at__date__lte=created_before)
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query)
                | Q(description__icontains=query)
                | Q(source_ticket_id__icontains=query)
                | Q(location__icontains=query)
                | Q(workstation__icontains=query)
                | Q(tags__icontains=query)
            )
        return queryset

    def perform_create(self, serializer):
        requested_reporter = serializer.validated_data.get("reporter")
        if self.request.user.can_manage_tickets and requested_reporter:
            reporter = requested_reporter
        else:
            reporter = self.request.user

        save_kwargs = {
            "reporter": reporter,
            "created_by": self.request.user,
            "status": TicketStatus.OPEN,
            "assignee": None,
            "resolved_by": None,
            "resolution_notes": "",
        }
        if not self.request.user.can_manage_tickets:
            save_kwargs["escalated_to"] = ""

        ticket = serializer.save(**save_kwargs)
        self._record_event(
            ticket=ticket,
            action="created",
            from_status="",
            to_status=TicketStatus.OPEN,
            note="Ticket created.",
            changes={"reference": ticket.reference},
        )

    def perform_update(self, serializer):
        before = {
            field: getattr(serializer.instance, field)
            for field in self.tracked_fields
        }
        ticket = serializer.save()
        old_status = before["status"]
        self._apply_derived_fields(ticket, old_status)

        changes = {}
        for field, old_value in before.items():
            new_value = getattr(ticket, field)
            if old_value != new_value:
                changes[field] = {
                    "from": self._json_value(old_value),
                    "to": self._json_value(new_value),
                }
        if changes:
            self._record_event(
                ticket=ticket,
                action="updated",
                from_status=old_status,
                to_status=ticket.status,
                changes=changes,
            )

    @staticmethod
    def _json_value(value):
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return value

    def _record_event(
        self,
        *,
        ticket,
        action,
        from_status="",
        to_status="",
        note="",
        changes=None,
    ):
        event = TicketEvent.objects.create(
            ticket=ticket,
            actor=self.request.user,
            action=action,
            from_status=from_status,
            to_status=to_status,
            note=note,
            changes=changes or {},
        )
        queue_ticket_notification(
            ticket=ticket,
            event_type=action,
            actor_name=self.request.user.display_name,
            note=note,
        )
        return event

    def _apply_derived_fields(self, ticket, old_status):
        now = timezone.now()
        update_fields = []

        if ticket.assignee and ticket.response_minutes is None:
            elapsed = max(0, int((now - ticket.created_at).total_seconds() // 60))
            ticket.response_minutes = elapsed
            update_fields.append("response_minutes")

        if ticket.status == TicketStatus.RESOLVED:
            if ticket.resolved_at is None:
                ticket.resolved_at = now
                update_fields.append("resolved_at")
            ticket.resolved_by = self.request.user
            update_fields.append("resolved_by")
            if ticket.downtime_end is None:
                ticket.downtime_end = now
                update_fields.append("downtime_end")
            if ticket.downtime_start and ticket.downtime_end:
                ticket.downtime_minutes = max(
                    0,
                    int(
                        (ticket.downtime_end - ticket.downtime_start).total_seconds()
                        // 60
                    ),
                )
                update_fields.append("downtime_minutes")
            if ticket.response_minutes is not None:
                ticket.resolution_minutes = max(
                    0,
                    int((now - ticket.created_at).total_seconds() // 60)
                    - ticket.response_minutes,
                )
                update_fields.append("resolution_minutes")
        elif ticket.status == TicketStatus.REOPENED and old_status != TicketStatus.REOPENED:
            ticket.reopen_count += 1
            ticket.resolved_at = None
            ticket.resolved_by = None
            ticket.downtime_end = None
            ticket.downtime_minutes = None
            ticket.resolution_minutes = None
            update_fields.extend(
                [
                    "reopen_count",
                    "resolved_at",
                    "resolved_by",
                    "downtime_end",
                    "downtime_minutes",
                    "resolution_minutes",
                ]
            )

        if update_fields:
            ticket.save(update_fields=[*set(update_fields), "updated_at"])

    def destroy(self, request, *args, **kwargs):
        raise MethodNotAllowed("DELETE", detail="Tickets are retained for audit history.")

    @action(detail=False, methods=["get"])
    def configuration(self, request):
        return Response(
            {
                "priorities": list(TicketPriority.values),
                "priority_colors": PRIORITY_COLORS,
                "ticket_types": list(TicketCategory.values),
                "impact_levels": list(TicketImpact.values),
                "impact_colors": IMPACT_COLORS,
                "root_causes": list(TicketRootCause.values),
                "statuses": list(TicketStatus.values),
                "status_colors": STATUS_COLORS,
                "workstations": WORKSTATIONS,
                "locations": LOCATIONS,
                "status_transitions": {
                    str(key): [str(value) for value in values]
                    for key, values in STATUS_TRANSITIONS.items()
                },
            }
        )

    @action(detail=False, methods=["get"])
    def summary(self, request):
        queryset = self.get_queryset()
        active_statuses = [
            TicketStatus.OPEN,
            TicketStatus.ASSIGNED,
            TicketStatus.IN_PROGRESS,
            TicketStatus.ON_HOLD,
            TicketStatus.REOPENED,
        ]
        return Response(
            queryset.aggregate(
                total=Count("id"),
                active=Count("id", filter=Q(status__in=active_statuses)),
                resolved=Count(
                    "id",
                    filter=Q(
                        status__in=[TicketStatus.RESOLVED, TicketStatus.CLOSED]
                    ),
                ),
                urgent=Count(
                    "id",
                    filter=Q(priority=TicketPriority.URGENT),
                ),
                unassigned=Count(
                    "id",
                    filter=Q(
                        assignee__isnull=True,
                        status__in=active_statuses,
                    ),
                ),
            )
        )

    @action(detail=False, methods=["get"])
    def analytics(self, request):
        try:
            period_days = int(request.query_params.get("period", "30"))
        except ValueError:
            raise ValidationError({"period": "Period must be 7, 30, or 90 days."})
        if period_days not in {7, 30, 90}:
            raise ValidationError({"period": "Period must be 7, 30, or 90 days."})

        start = timezone.now() - timedelta(days=period_days)
        queryset = self.get_queryset().filter(created_at__gte=start)
        active_statuses = [
            TicketStatus.OPEN,
            TicketStatus.ASSIGNED,
            TicketStatus.IN_PROGRESS,
            TicketStatus.ON_HOLD,
            TicketStatus.REOPENED,
        ]

        def grouped(field_name):
            return list(
                queryset.values(field_name)
                .annotate(count=Count("id"))
                .order_by("-count", field_name)
            )

        metrics = queryset.aggregate(
            total=Count("id"),
            active=Count("id", filter=Q(status__in=active_statuses)),
            resolved=Count(
                "id",
                filter=Q(status__in=[TicketStatus.RESOLVED, TicketStatus.CLOSED]),
            ),
            average_downtime=Avg("downtime_minutes"),
            average_response=Avg("response_minutes"),
            average_resolution=Avg("resolution_minutes"),
        )
        trend = list(
            queryset.annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(count=Count("id"))
            .order_by("day")
        )
        resolved_by = list(
            queryset.filter(resolved_by__isnull=False)
            .values(
                "resolved_by__email",
                "resolved_by__first_name",
                "resolved_by__last_name",
            )
            .annotate(count=Count("id"))
            .order_by("-count", "resolved_by__email")
        )

        return Response(
            {
                "period_days": period_days,
                "metrics": {
                    key: (
                        round(float(value), 1)
                        if value is not None and key.startswith("average_")
                        else value
                    )
                    for key, value in metrics.items()
                },
                "by_status": grouped("status"),
                "by_priority": grouped("priority"),
                "by_category": grouped("category"),
                "by_workstation": grouped("workstation"),
                "trend": trend,
                "resolved_by": resolved_by,
            }
        )

    @staticmethod
    def _csv_safe(value):
        text = "" if value is None else str(value)
        if text.startswith(("=", "+", "-", "@")):
            return f"'{text}"
        return text

    @action(detail=False, methods=["get"])
    def export(self, request):
        queryset = self.get_queryset()[:10000]
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = (
            'attachment; filename="nvgs_tickets_export.csv"'
        )
        response.write("\ufeff")
        writer = csv.writer(response)
        writer.writerow(
            [
                "Ticket ID",
                "Created",
                "Updated",
                "Title",
                "Description",
                "Category",
                "Priority",
                "Status",
                "Workstation",
                "Location",
                "Reporter",
                "Reporter Email",
                "Assignee",
                "Resolution Notes",
                "Root Cause",
                "Downtime Minutes",
                "Tags",
            ]
        )
        for ticket in queryset:
            writer.writerow(
                [
                    self._csv_safe(ticket.reference),
                    ticket.created_at.isoformat(),
                    ticket.updated_at.isoformat(),
                    self._csv_safe(ticket.title),
                    self._csv_safe(ticket.description),
                    ticket.category,
                    ticket.priority,
                    ticket.status,
                    self._csv_safe(ticket.workstation),
                    self._csv_safe(ticket.location),
                    self._csv_safe(ticket.reporter.display_name),
                    self._csv_safe(ticket.reporter.email),
                    self._csv_safe(
                        ticket.assignee.display_name if ticket.assignee else ""
                    ),
                    self._csv_safe(ticket.resolution_notes),
                    ticket.root_cause,
                    ticket.downtime_minutes,
                    self._csv_safe(ticket.tags),
                ]
            )
        return response

    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        ticket = self.get_object()
        return self._assign_ticket(ticket, request.data.get("assignee"))

    def _assign_ticket(self, ticket, assignee_id):
        previous_assignee_id = ticket.assignee_id
        try:
            assignee = User.objects.get(
                pk=assignee_id,
                is_active=True,
                role__in=[UserRole.TEAM, UserRole.SYSTEM_ADMIN],
            )
        except (User.DoesNotExist, TypeError, ValueError):
            raise ValidationError(
                {"assignee": "Select an active Tech Team, TL, or Manager account."}
            )

        old_status = ticket.status
        ticket.assignee = assignee
        if old_status in {TicketStatus.OPEN, TicketStatus.REOPENED}:
            ticket.status = TicketStatus.ASSIGNED
        ticket.save(update_fields=["assignee", "status", "updated_at"])
        self._apply_derived_fields(ticket, old_status)
        self._record_event(
            ticket=ticket,
            action="assigned",
            from_status=old_status,
            to_status=ticket.status,
            note=f"Assigned to {assignee.display_name}.",
            changes={
                "assignee_id": {
                    "from": previous_assignee_id,
                    "to": assignee.id,
                }
            },
        )
        return Response(self.get_serializer(ticket).data)

    @action(detail=True, methods=["post"], url_path="assign-to-me")
    def assign_to_me(self, request, pk=None):
        ticket = self.get_object()
        return self._assign_ticket(ticket, request.user.pk)

    @action(detail=True, methods=["post"])
    def transition(self, request, pk=None):
        ticket = self.get_object()
        old_status = ticket.status
        data = {
            key: value
            for key, value in request.data.items()
            if key
            in {
                "status",
                "resolution_notes",
                "root_cause",
                "downtime_end",
            }
        }
        serializer = self.get_serializer(ticket, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        ticket.refresh_from_db()
        self._record_event(
            ticket=ticket,
            action="status_changed",
            from_status=old_status,
            to_status=ticket.status,
            note=str(request.data.get("note", ""))[:2000],
        )
        return Response(self.get_serializer(ticket).data)

    @action(detail=True, methods=["post"])
    def escalate(self, request, pk=None):
        ticket = self.get_object()
        ticket.escalated_count += 1
        ticket.escalated_to = str(request.data.get("escalated_to", ""))[:180]
        ticket.save(
            update_fields=["escalated_count", "escalated_to", "updated_at"]
        )
        self._record_event(
            ticket=ticket,
            action="escalated",
            from_status=ticket.status,
            to_status=ticket.status,
            note=str(request.data.get("note", ""))[:2000],
            changes={
                "escalated_count": ticket.escalated_count,
                "escalated_to": ticket.escalated_to,
            },
        )
        return Response(self.get_serializer(ticket).data)

    @action(detail=True, methods=["get"])
    def history(self, request, pk=None):
        ticket = self.get_object()
        events = ticket.events.select_related("actor").all()
        return Response(TicketEventSerializer(events, many=True).data)

    @action(detail=False, methods=["post"], url_path="bulk-status")
    def bulk_status(self, request):
        ticket_ids = request.data.get("ticket_ids")
        new_status = request.data.get("status")
        if not isinstance(ticket_ids, list) or not ticket_ids:
            raise ValidationError({"ticket_ids": "Provide at least one ticket ID."})
        if len(ticket_ids) > 50:
            raise ValidationError({"ticket_ids": "The maximum is 50 tickets."})

        results = []
        for ticket in self.get_queryset().filter(pk__in=ticket_ids):
            old_status = ticket.status
            data = {"status": new_status}
            if "resolution_notes" in request.data:
                data["resolution_notes"] = request.data["resolution_notes"]
            serializer = self.get_serializer(
                ticket,
                data=data,
                partial=True,
            )
            if serializer.is_valid():
                self.perform_update(serializer)
                ticket.refresh_from_db()
                self._record_event(
                    ticket=ticket,
                    action="status_changed",
                    from_status=old_status,
                    to_status=ticket.status,
                    note=str(request.data.get("note", ""))[:2000],
                )
                results.append({"id": ticket.pk, "ok": True})
            else:
                results.append(
                    {"id": ticket.pk, "ok": False, "errors": serializer.errors}
                )
        return Response(results)

    @action(detail=True, methods=["get", "post"])
    def comments(self, request, pk=None):
        ticket = self.get_object()
        if request.method == "GET":
            comments = ticket.comments.select_related("author").all()
            if not request.user.can_manage_tickets:
                comments = comments.filter(is_internal=False)
            return Response(TicketCommentSerializer(comments, many=True).data)

        serializer = TicketCommentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if (
            serializer.validated_data.get("is_internal")
            and not request.user.can_manage_tickets
        ):
            raise ValidationError(
                {
                    "is_internal": (
                        "Only the Tech Team, TLs, and Managers can add internal notes."
                    )
                }
            )
        comment = serializer.save(ticket=ticket, author=request.user)
        self._record_event(
            ticket=ticket,
            action=(
                "internal_comment_added"
                if comment.is_internal
                else "comment_added"
            ),
            from_status=ticket.status,
            to_status=ticket.status,
            note=comment.body[:80],
            changes={"internal": comment.is_internal},
        )
        return Response(
            TicketCommentSerializer(comment).data,
            status=status.HTTP_201_CREATED,
        )
