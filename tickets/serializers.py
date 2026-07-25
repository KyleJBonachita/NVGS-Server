from rest_framework import serializers

from accounts.models import User, UserRole
from accounts.serializers import UserSerializer

from .models import (
    STATUS_TRANSITIONS,
    Ticket,
    TicketComment,
    TicketEvent,
    TicketStatus,
)


class TicketCommentSerializer(serializers.ModelSerializer):
    comment_id = serializers.SerializerMethodField()
    author = UserSerializer(read_only=True)

    class Meta:
        model = TicketComment
        fields = [
            "id",
            "comment_id",
            "author",
            "body",
            "is_internal",
            "created_at",
        ]
        read_only_fields = ["id", "comment_id", "author", "created_at"]

    def get_comment_id(self, obj):
        return obj.source_comment_id or f"CMT-{obj.pk:08d}"


class TicketEventSerializer(serializers.ModelSerializer):
    event_id = serializers.SerializerMethodField()
    actor = UserSerializer(read_only=True)

    class Meta:
        model = TicketEvent
        fields = [
            "id",
            "event_id",
            "action",
            "from_status",
            "to_status",
            "actor",
            "note",
            "changes",
            "created_at",
        ]

    def get_event_id(self, obj):
        return obj.source_event_id or f"EVT-{obj.pk:07d}"


class TicketSerializer(serializers.ModelSerializer):
    reference = serializers.CharField(read_only=True)
    ticket_id = serializers.CharField(source="reference", read_only=True)
    reporter = UserSerializer(read_only=True)
    reporter_id = serializers.PrimaryKeyRelatedField(
        source="reporter",
        queryset=User.objects.filter(is_active=True),
        write_only=True,
        required=False,
    )
    created_by = UserSerializer(read_only=True)
    assignee = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(
            is_active=True,
            role__in=[UserRole.TEAM, UserRole.SYSTEM_ADMIN],
        ),
        allow_null=True,
        required=False,
    )
    assignee_details = UserSerializer(source="assignee", read_only=True)
    resolved_by = UserSerializer(read_only=True)
    comment_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Ticket
        fields = [
            "id",
            "reference",
            "ticket_id",
            "reporter",
            "reporter_id",
            "created_by",
            "assignee",
            "assignee_details",
            "resolved_by",
            "title",
            "description",
            "category",
            "priority",
            "status",
            "location",
            "workstation",
            "downtime_start",
            "downtime_end",
            "downtime_minutes",
            "resolution_notes",
            "resolution_minutes",
            "response_minutes",
            "escalated_count",
            "escalated_to",
            "reopen_count",
            "tags",
            "root_cause",
            "impact_level",
            "affected_stations",
            "comment_count",
            "created_at",
            "updated_at",
            "resolved_at",
        ]
        read_only_fields = [
            "id",
            "reference",
            "ticket_id",
            "reporter",
            "created_by",
            "assignee_details",
            "resolved_by",
            "downtime_minutes",
            "resolution_minutes",
            "response_minutes",
            "escalated_count",
            "reopen_count",
            "comment_count",
            "created_at",
            "updated_at",
            "resolved_at",
        ]

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        if (
            request
            and request.user.is_authenticated
            and not request.user.can_manage_tickets
        ):
            fields.pop("reporter_id", None)
            for field_name in [
                "assignee",
                "status",
                "downtime_end",
                "resolution_notes",
                "escalated_to",
                "root_cause",
            ]:
                fields[field_name].read_only = True
        return fields

    def validate(self, attrs):
        if self.instance is not None and "reporter" in attrs:
            raise serializers.ValidationError(
                {"reporter_id": "A ticket reporter cannot be changed after creation."}
            )
        status_value = attrs.get(
            "status",
            self.instance.status if self.instance else TicketStatus.OPEN,
        )
        resolution_notes = attrs.get(
            "resolution_notes",
            self.instance.resolution_notes if self.instance else "",
        )
        if status_value in {TicketStatus.RESOLVED, TicketStatus.CLOSED}:
            if not resolution_notes.strip():
                raise serializers.ValidationError(
                    {
                        "resolution_notes": (
                            "Resolution notes are required before resolving a ticket."
                        )
                    }
                )
        if self.instance is not None and "status" in attrs:
            old_status = self.instance.status
            new_status = attrs["status"]
            if old_status != new_status and new_status not in STATUS_TRANSITIONS.get(
                old_status, set()
            ):
                raise serializers.ValidationError(
                    {"status": f"Cannot transition from {old_status} to {new_status}."}
                )

        downtime_start = attrs.get(
            "downtime_start",
            self.instance.downtime_start if self.instance else None,
        )
        downtime_end = attrs.get(
            "downtime_end",
            self.instance.downtime_end if self.instance else None,
        )
        if downtime_start and downtime_end and downtime_end < downtime_start:
            raise serializers.ValidationError(
                {"downtime_end": "Downtime end cannot be before downtime start."}
            )
        return attrs
