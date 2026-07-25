from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from .models import (
    Ticket,
    TicketComment,
    TicketEvent,
    TicketPriority,
    TicketStatus,
)
from .permissions import CanManageTickets
from .serializers import TicketCommentSerializer, TicketSerializer


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
        "area",
        "workstation",
        "resolution",
    ]

    def get_permissions(self):
        if self.action in {"update", "partial_update"}:
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
            queryset = queryset.filter(reporter=user)

        status_value = self.request.query_params.get("status")
        priority = self.request.query_params.get("priority")
        assignee = self.request.query_params.get("assignee")
        reporter = self.request.query_params.get("reporter")
        query = self.request.query_params.get("q")

        if status_value:
            queryset = queryset.filter(status=status_value)
        if priority:
            queryset = queryset.filter(priority=priority)
        if assignee and user.can_manage_tickets:
            queryset = queryset.filter(assignee_id=assignee)
        if reporter and user.can_manage_tickets:
            queryset = queryset.filter(reporter_id=reporter)
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query)
                | Q(description__icontains=query)
                | Q(area__icontains=query)
                | Q(workstation__icontains=query)
            )
        return queryset

    def perform_create(self, serializer):
        requested_reporter = serializer.validated_data.get("reporter")
        if self.request.user.can_manage_tickets and requested_reporter:
            reporter = requested_reporter
        else:
            reporter = self.request.user

        save_kwargs = {"reporter": reporter}
        if not self.request.user.can_manage_tickets:
            save_kwargs.update(
                {
                    "assignee": None,
                    "priority": TicketPriority.NORMAL,
                    "status": TicketStatus.NEW,
                    "resolution": "",
                }
            )

        ticket = serializer.save(**save_kwargs)
        TicketEvent.objects.create(
            ticket=ticket,
            actor=self.request.user,
            action="created",
            changes={"reference": ticket.reference},
        )

    def perform_update(self, serializer):
        before = {
            field: getattr(serializer.instance, field)
            for field in self.tracked_fields
        }
        ticket = serializer.save()
        if (
            ticket.status in {TicketStatus.RESOLVED, TicketStatus.CLOSED}
            and ticket.resolved_at is None
        ):
            ticket.resolved_at = timezone.now()
            ticket.save(update_fields=["resolved_at", "updated_at"])
        elif (
            ticket.status not in {TicketStatus.RESOLVED, TicketStatus.CLOSED}
            and ticket.resolved_at is not None
        ):
            ticket.resolved_at = None
            ticket.save(update_fields=["resolved_at", "updated_at"])

        changes = {}
        for field, old_value in before.items():
            new_value = getattr(ticket, field)
            if old_value != new_value:
                changes[field] = {"from": old_value, "to": new_value}
        if changes:
            TicketEvent.objects.create(
                ticket=ticket,
                actor=self.request.user,
                action="updated",
                changes=changes,
            )

    def destroy(self, request, *args, **kwargs):
        raise MethodNotAllowed("DELETE", detail="Tickets are retained for audit history.")

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
                {"is_internal": "Only the Tech Team and TLs can add internal notes."}
            )
        comment = serializer.save(ticket=ticket, author=request.user)
        TicketEvent.objects.create(
            ticket=ticket,
            actor=request.user,
            action="comment_added",
            changes={"internal": comment.is_internal},
        )
        return Response(
            TicketCommentSerializer(comment).data,
            status=status.HTTP_201_CREATED,
        )
