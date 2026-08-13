from __future__ import annotations

import logging

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods

from accounts.web_views import _secure_page

from .services import (
    DownloadUploadError,
    list_download_entries,
    store_uploaded_files,
)

logger = logging.getLogger(__name__)


@never_cache
@ensure_csrf_cookie
@login_required
@require_http_methods(["GET", "POST"])
def download_manager(request):
    if not request.user.can_manage_tickets:
        raise PermissionDenied(
            "Only the Tech Team, TLs, Managers, and system administrators "
            "can upload download-server files."
        )

    if request.method == "POST":
        try:
            stored = store_uploaded_files(
                request.FILES.getlist("files"),
                conflict_policy=request.POST.get("conflict_policy", "rename"),
            )
        except DownloadUploadError as exc:
            return JsonResponse({"ok": False, "error": str(exc)}, status=400)

        logger.info(
            "Download library upload: user=%s files=%s policy=%s",
            request.user.email,
            [item.name for item in stored],
            request.POST.get("conflict_policy", "rename"),
        )
        return JsonResponse(
            {
                "ok": True,
                "files": [
                    {"name": item.name, "size": item.size} for item in stored
                ],
            }
        )

    entries = list_download_entries()
    response = render(
        request,
        "downloads/manage.html",
        {
            "entries": entries,
            "existing_root_names": [
                entry.name for entry in entries if "/" not in entry.relative_path
            ],
        },
    )
    return _secure_page(response)

