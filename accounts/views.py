import logging
import secrets
import time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.conf import settings
from django.contrib.auth import login, logout
from django.db import IntegrityError, transaction
from django.http import HttpResponse, HttpResponseRedirect
from django.middleware.csrf import get_token
from django.shortcuts import redirect, render
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from .appscript_sso import BridgeTokenError, verify_bridge_token
from .forms import SsoOnboardingForm
from .models import User, UserRole
from .serializers import LoginSerializer, ProfileSerializer, UserSerializer

logger = logging.getLogger(__name__)


def _private_response(response):
    response["Cache-Control"] = "no-store"
    response["Pragma"] = "no-cache"
    response["Referrer-Policy"] = "same-origin"
    response["X-Content-Type-Options"] = "nosniff"
    return response


def _bridge_error(message: str, status_code: int):
    return _private_response(
        HttpResponse(
            f"NVGS login failed: {message}",
            status=status_code,
            content_type="text/plain; charset=utf-8",
        )
    )


def _bridge_token_error_message(error: BridgeTokenError) -> str:
    reason = str(error)
    if reason == "Invalid login signature.":
        return (
            "The Apps Script and Ubuntu signing secrets do not match. "
            "Run ./scripts/appscript-login-setup.sh prepare on Ubuntu and "
            "update NVGS_BRIDGE_SECRET in Apps Script."
        )
    if reason in {
        "Login token is not active yet.",
        "Login token is too old.",
        "Login token has expired.",
        "Invalid login lifetime.",
    }:
        return (
            "The login response expired or the Ubuntu clock is incorrect. "
            "Start login again and check timedatectl status on Ubuntu."
        )
    if reason == "Login state did not match this browser.":
        return (
            "This login was started in another or expired browser session. "
            "Return to the NVGS login page and start again in the same browser tab."
        )
    if reason in {"Invalid login issuer.", "Invalid login audience."}:
        return (
            "The Apps Script bridge settings do not match NVGS. Run "
            "./scripts/appscript-login-setup.sh prepare and update the Script Properties."
        )
    if reason == "Login email domain was not approved.":
        return "The verified Google account is not in the approved NVIDIA domain."
    return "The signed login response was invalid. Start a fresh login and try again."


def _needs_onboarding(user: User) -> bool:
    return (
        not user.first_name.strip()
        or not user.last_name.strip()
        or not user.has_usable_password()
    )


@require_GET
def appscript_sso_start(request):
    if not settings.APPSCRIPT_SSO_ENABLED:
        return _bridge_error("Apps Script login is not enabled.", 503)

    if request.user.is_authenticated:
        logout(request)

    request.session.pop("appscript_onboarding_user_id", None)
    request.session.pop("appscript_onboarding_started_at", None)
    state = secrets.token_urlsafe(32)
    request.session["appscript_sso_state"] = state
    request.session["appscript_sso_started_at"] = int(time.time())

    parts = urlsplit(settings.APPSCRIPT_SSO_URL)
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key not in {"nvgs_action", "state"}
    ]
    query.extend(
        [
            ("nvgs_action", "login"),
            ("state", state),
        ]
    )
    destination = urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(query),
            parts.fragment,
        )
    )
    return _private_response(HttpResponseRedirect(destination))


@require_GET
def appscript_sso_consume(request):
    if not settings.APPSCRIPT_SSO_ENABLED:
        return _bridge_error("Apps Script login is not enabled.", 503)
    content_nonce = secrets.token_urlsafe(24)
    response = render(
        request,
        "accounts/appscript_sso_consume.html",
        {"content_nonce": content_nonce},
    )
    response["Content-Security-Policy"] = (
        "default-src 'none'; "
        f"script-src 'nonce-{content_nonce}'; "
        f"style-src 'nonce-{content_nonce}'; "
        "form-action 'self'; "
        "base-uri 'none'; "
        "frame-ancestors 'none'"
    )
    return _private_response(response)


# The signed assertion and one-time browser-session state are this endpoint's
# CSRF protection. Exempting only this handoff avoids cross-site cookie failures.
@csrf_exempt
@require_POST
def appscript_sso_callback(request):
    if not settings.APPSCRIPT_SSO_ENABLED:
        return _bridge_error("Apps Script login is not enabled.", 503)

    expected_state = request.session.pop("appscript_sso_state", "")
    started_at = request.session.pop("appscript_sso_started_at", 0)
    current_time = int(time.time())
    if (
        not expected_state
        or not isinstance(started_at, int)
        or started_at < current_time - settings.APPSCRIPT_SSO_STATE_TTL_SECONDS
        or started_at > current_time + settings.APPSCRIPT_SSO_CLOCK_SKEW_SECONDS
    ):
        return _bridge_error("This login attempt expired. Start again.", 400)

    try:
        identity = verify_bridge_token(
            request.POST.get("token", ""),
            expected_state,
            now=current_time,
        )
    except BridgeTokenError as exc:
        logger.warning("Rejected Apps Script login assertion: %s", exc)
        return _bridge_error(_bridge_token_error_message(exc), 400)

    try:
        user = User.objects.get(email=identity.email)
    except User.DoesNotExist:
        if not settings.APPSCRIPT_SSO_AUTO_CREATE_USERS:
            return _bridge_error(
                "Your verified account has not been provisioned.",
                403,
            )
        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    email=identity.email,
                    password=None,
                    role=UserRole.AGENT,
                )
        except IntegrityError:
            user = User.objects.get(email=identity.email)

    if not user.is_active:
        return _bridge_error("This NVGS account is disabled.", 403)

    if _needs_onboarding(user):
        request.session["appscript_onboarding_user_id"] = user.pk
        request.session["appscript_onboarding_started_at"] = current_time
        return _private_response(redirect("appscript-sso-onboarding"))
    login(
        request,
        user,
        backend="django.contrib.auth.backends.ModelBackend",
    )
    logger.info("Apps Script SSO login succeeded for %s.", user.email)
    return _private_response(
        HttpResponseRedirect(settings.APPSCRIPT_SSO_SUCCESS_REDIRECT)
    )


@require_http_methods(["GET", "POST"])
def appscript_sso_onboarding(request):
    if not settings.APPSCRIPT_SSO_ENABLED:
        return _bridge_error("Apps Script login is not enabled.", 503)

    user_id = request.session.get("appscript_onboarding_user_id")
    started_at = request.session.get("appscript_onboarding_started_at")
    current_time = int(time.time())
    onboarding_ttl = settings.APPSCRIPT_SSO_ONBOARDING_TTL_SECONDS
    if (
        isinstance(user_id, bool)
        or not isinstance(user_id, int)
        or not isinstance(started_at, int)
        or started_at < current_time - onboarding_ttl
        or started_at > current_time + settings.APPSCRIPT_SSO_CLOCK_SKEW_SECONDS
    ):
        request.session.pop("appscript_onboarding_user_id", None)
        request.session.pop("appscript_onboarding_started_at", None)
        return _bridge_error("Profile setup expired. Start Google login again.", 400)

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return _bridge_error("The verified NVGS account no longer exists.", 400)
    if not user.is_active:
        return _bridge_error("This NVGS account is disabled.", 403)
    if not _needs_onboarding(user):
        request.session.pop("appscript_onboarding_user_id", None)
        request.session.pop("appscript_onboarding_started_at", None)
        login(
            request,
            user,
            backend="django.contrib.auth.backends.ModelBackend",
        )
        return _private_response(
            HttpResponseRedirect(settings.APPSCRIPT_SSO_SUCCESS_REDIRECT)
        )

    if request.method == "POST":
        form = SsoOnboardingForm(request.POST, user=user)
        if form.is_valid():
            user = form.save()
            request.session.pop("appscript_onboarding_user_id", None)
            request.session.pop("appscript_onboarding_started_at", None)
            login(
                request,
                user,
                backend="django.contrib.auth.backends.ModelBackend",
            )
            logger.info("NVGS onboarding completed for %s.", user.email)
            return _private_response(
                HttpResponseRedirect(settings.APPSCRIPT_SSO_SUCCESS_REDIRECT)
            )
    else:
        form = SsoOnboardingForm(
            user=user,
            initial={
                "first_name": user.first_name,
                "last_name": user.last_name,
            },
        )

    content_nonce = secrets.token_urlsafe(24)
    response = render(
        request,
        "accounts/appscript_onboarding.html",
        {
            "content_nonce": content_nonce,
            "form": form,
            "verified_email": user.email,
        },
    )
    response["Content-Security-Policy"] = (
        "default-src 'none'; "
        f"style-src 'nonce-{content_nonce}'; "
        "form-action 'self'; "
        "base-uri 'none'; "
        "frame-ancestors 'none'"
    )
    return _private_response(response)


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

    def patch(self, request):
        serializer = ProfileSerializer(
            request.user,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
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
