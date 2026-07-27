"""Small shared alert helper with no third-party dependencies."""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import urllib.request
from datetime import datetime, timezone
from html import escape
from pathlib import Path


def log(message: str) -> None:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"{timestamp} {message}", flush=True)


def server_name() -> str:
    return os.getenv("NVGS_SERVER_NAME", socket.gethostname())


def setting_enabled(name: str, default: bool = False) -> bool:
    value = os.getenv(name, "true" if default else "false").strip().lower()
    return value in {"1", "true", "yes", "on"}


def desktop_user_id(desktop_user: str) -> str | None:
    try:
        user_id = subprocess.check_output(
            ["id", "-u", desktop_user],
            text=True,
            timeout=3,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        log(f"Desktop alert skipped: user {desktop_user!r} was not found.")
        return None

    if not user_id.isdigit():
        log("Desktop alert skipped: the desktop user ID was invalid.")
        return None
    return user_id


def send_fullscreen_alert(
    title: str,
    detail: str,
    level: str = "warning",
) -> bool:
    """Send a warning to the controller's full-screen desktop overlay."""
    if level.lower() != "warning" or not setting_enabled(
        "NVGS_FULLSCREEN_ALERTS",
        default=True,
    ):
        return False

    desktop_user = os.getenv("NVGS_DESKTOP_USER", "").strip()
    if not desktop_user:
        return False

    user_id = desktop_user_id(desktop_user)
    if user_id is None:
        return False

    socket_path = Path("/run/user") / user_id / "nvgs-alert-overlay.sock"
    if not socket_path.is_socket():
        return False

    payload = json.dumps(
        {
            "title": title,
            "detail": detail,
            "level": level,
            "server": server_name(),
        }
    ).encode("utf-8")
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as client:
            client.sendto(payload, str(socket_path))
    except OSError:
        log("Full-screen alert delivery failed.")
        return False
    return True


def send_desktop_notification(
    title: str,
    detail: str,
    level: str = "warning",
) -> bool:
    """Send an alert to the configured logged-in Ubuntu desktop user."""
    if not setting_enabled("NVGS_DESKTOP_NOTIFICATIONS"):
        return False

    desktop_user = os.getenv("NVGS_DESKTOP_USER", "").strip()
    if not desktop_user:
        log("Desktop notification skipped: NVGS_DESKTOP_USER is not configured.")
        return False

    runuser = shutil.which("runuser")
    notify_send = shutil.which("notify-send")
    if not runuser or not notify_send:
        log("Desktop notification skipped: notify-send or runuser was not found.")
        return False

    user_id = desktop_user_id(desktop_user)
    if user_id is None:
        return False

    runtime_dir = Path("/run/user") / user_id
    session_bus = runtime_dir / "bus"
    if not session_bus.exists():
        log("Desktop notification skipped: no active graphical session was found.")
        return False

    is_warning = level.lower() == "warning"
    urgency = "critical" if is_warning else "normal"
    icon = "dialog-warning" if is_warning else "dialog-information"
    sound = "dialog-warning" if is_warning else "complete"

    command = [
        runuser,
        "-u",
        desktop_user,
        "--",
        "env",
        f"XDG_RUNTIME_DIR={runtime_dir}",
        f"DBUS_SESSION_BUS_ADDRESS=unix:path={session_bus}",
        notify_send,
        "--app-name=NVGS Server",
        f"--urgency={urgency}",
        f"--icon={icon}",
        f"--hint=string:sound-name:{sound}",
        escape(f"NVGS {title}"),
        escape(detail),
    ]
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        log("Desktop notification delivery failed.")
        return False

    if completed.returncode != 0:
        log("Desktop notification was rejected by the graphical session.")
        return False
    return True


def send_alert(title: str, detail: str, level: str = "warning") -> bool:
    """Log every alert, notify the desktop, and optionally send a webhook."""
    message = f"[{level.upper()}] {server_name()}: {title} - {detail}"
    log(message)
    send_fullscreen_alert(title, detail, level)
    send_desktop_notification(title, detail, level)

    webhook_url = os.getenv("NVGS_ALERT_WEBHOOK_URL", "").strip()
    if not webhook_url:
        return False

    payload = json.dumps(
        {
            "text": message,
            "source": "NVGS Server",
            "level": level,
            "server": server_name(),
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "NVGS-Server-Monitor/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            if 200 <= response.status < 300:
                return True
            log(f"Webhook returned HTTP {response.status}.")
    except Exception as exc:
        # Do not crash the monitor when the same network needed for the alert is
        # unavailable.
        log(f"Webhook delivery failed: {type(exc).__name__}.")
    return False


def fatal(message: str) -> None:
    log(f"FATAL: {message}")
    raise SystemExit(1)


if __name__ == "__main__":
    fatal("This module is imported by the NVGS monitoring services.")
