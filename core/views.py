from django.db import connection
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


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

