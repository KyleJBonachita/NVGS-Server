from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET

from accounts.web_views import _secure_page


@never_cache
@ensure_csrf_cookie
@login_required
@require_GET
def dashboard(request):
    response = render(request, "tickets/dashboard.html")
    return _secure_page(response)
