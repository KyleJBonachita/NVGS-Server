from django.conf import settings
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET


def _secure_page(response):
    response["Cache-Control"] = "no-store"
    response["Pragma"] = "no-cache"
    response["Referrer-Policy"] = "same-origin"
    response["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "font-src 'self'; "
        "form-action 'self'; "
        "base-uri 'none'; "
        "frame-ancestors 'none'"
    )
    return response


@require_GET
def home(request):
    destination = "ticket-dashboard" if request.user.is_authenticated else "login-page"
    return redirect(destination)


@never_cache
@ensure_csrf_cookie
@require_GET
def login_page(request):
    if request.user.is_authenticated:
        return redirect("ticket-dashboard")
    response = render(
        request,
        "accounts/login.html",
        {"appscript_sso_enabled": settings.APPSCRIPT_SSO_ENABLED},
    )
    return _secure_page(response)
