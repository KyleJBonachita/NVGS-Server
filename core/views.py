from django.conf import settings
from django.db import connection
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from tickets.models import TicketNotification
from tickets.notifications import notification_configuration


class HealthView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except Exception:
            return Response(
                {"status": "unhealthy", "database": "unavailable"},
                status=503,
            )
        return Response({"status": "ok", "database": "available"})


class SystemStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.can_manage_tickets:
            raise PermissionDenied(
                "Only the Tech Team, TLs, and Managers can view system status."
            )
        pending = TicketNotification.objects.filter(sent_at__isnull=True)
        notification_mode, notification_configured = notification_configuration()
        return Response(
            {
                "environment": settings.ENVIRONMENT,
                "server_address": request.get_host(),
                "database": "available",
                "appscript_login_enabled": settings.APPSCRIPT_SSO_ENABLED,
                "ticket_notification_mode": notification_mode,
                "ticket_notifications_configured": notification_configured,
                "pending_notifications": pending.filter(
                    attempts__lt=settings.TICKET_NOTIFICATION_MAX_ATTEMPTS
                ).count(),
                "failed_notifications": pending.filter(attempts__gt=0).count(),
                "abandoned_notifications": pending.filter(
                    attempts__gte=settings.TICKET_NOTIFICATION_MAX_ATTEMPTS
                ).count(),
            }
        )
