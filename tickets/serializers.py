from rest_framework import serializers

from accounts.models import User, UserRole
from accounts.serializers import UserSerializer

from .models import (
    Ticket,
    TicketComment,
    TicketStatus,
)


class TicketCommentSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)

    class Meta:
        model = TicketComment
        fields = ["id", "author", "body", "is_internal", "created_at"]
        read_only_fields = ["id", "author", "created_at"]


class TicketSerializer(serializers.ModelSerializer):
    reference = serializers.CharField(read_only=True)
    reporter = UserSerializer(read_only=True)
    reporter_id = serializers.PrimaryKeyRelatedField(
        source="reporter",
        queryset=User.objects.filter(is_active=True),
        write_only=True,
        required=False,
    )
    assignee = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(
            is_active=True,
            role__in=[UserRole.TEAM, UserRole.SYSTEM_ADMIN],
        ),
        allow_null=True,
        required=False,
    )
    assignee_details = UserSerializer(source="assignee", read_only=True)
    comment_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Ticket
        fields = [
            "id",
            "reference",
            "reporter",
            "reporter_id",
            "assignee",
            "assignee_details",
            "title",
            "description",
            "category",
            "priority",
            "status",
            "area",
            "workstation",
            "resolution",
            "comment_count",
            "created_at",
            "updated_at",
            "resolved_at",
        ]
        read_only_fields = [
            "id",
            "reference",
            "reporter",
            "assignee_details",
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
            for field_name in ["assignee", "priority", "status", "resolution"]:
                fields[field_name].read_only = True
        return fields

    def validate(self, attrs):
        if self.instance is not None and "reporter" in attrs:
            raise serializers.ValidationError(
                {"reporter_id": "A ticket reporter cannot be changed after creation."}
            )
        status_value = attrs.get(
            "status",
            self.instance.status if self.instance else TicketStatus.NEW,
        )
        resolution = attrs.get(
            "resolution",
            self.instance.resolution if self.instance else "",
        )
        if status_value in {TicketStatus.RESOLVED, TicketStatus.CLOSED}:
            if not resolution.strip():
                raise serializers.ValidationError(
                    {"resolution": "A resolution is required before resolving a ticket."}
                )
        return attrs
