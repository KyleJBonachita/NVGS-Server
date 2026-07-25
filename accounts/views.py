from django.contrib.auth import login, logout
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from .models import User, UserRole
from .serializers import LoginSerializer, UserSerializer


class LoginRateThrottle(AnonRateThrottle):
    scope = "login"


class CsrfView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"csrf_token": get_token(request)})


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        login(request, user)
        return Response(UserSerializer(user).data, status=status.HTTP_200_OK)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class UserListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.can_manage_tickets:
            raise PermissionDenied(
                "Only the Tech Team, TLs, and Managers can list users."
            )
        users = User.objects.filter(is_active=True).order_by("email")
        return Response(UserSerializer(users, many=True).data)


class AssignableUserListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.can_manage_tickets:
            raise PermissionDenied(
                "Only the Tech Team, TLs, and Managers can list assignees."
            )
        users = User.objects.filter(
            is_active=True,
            role__in=[UserRole.TEAM, UserRole.SYSTEM_ADMIN],
        ).order_by("email")
        return Response(UserSerializer(users, many=True).data)
