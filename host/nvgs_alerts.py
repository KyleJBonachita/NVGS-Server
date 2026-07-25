"""Small shared alert helper with no third-party dependencies."""

from __future__ import annotations

import json
import os
import socket
import urllib.request
from datetime import datetime, timezone


def log(message: str) -> None:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"{timestamp} {message}", flush=True)


def server_name() -> str:
    return os.getenv("NVGS_SERVER_NAME", socket.gethostname())


def send_alert(title: str, detail: str, level: str = "warning") -> bool:
    """Log every alert locally and optionally send it to a webhook."""
    message = f"[{level.upper()}] {server_name()}: {title} - {detail}"
    log(message)

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
