#!/usr/bin/env python3
"""Watch NVGS from a second device and report outages through a webhook."""

from __future__ import annotations

import json
import os
import socket
import ssl
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def log(message: str) -> None:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"{timestamp} {message}", flush=True)


def integer_setting(name: str, default: int, minimum: int) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except ValueError:
        return max(minimum, default)


def send_webhook(message: str, level: str) -> bool:
    webhook_url = os.getenv("NVGS_REMOTE_WEBHOOK_URL", "").strip()
    if not webhook_url:
        log(f"Webhook is not configured. Alert was: {message}")
        return False
    payload = json.dumps(
        {
            "text": message,
            "source": "NVGS External Watcher",
            "level": level,
            "server": os.getenv("NVGS_REMOTE_SERVER_NAME", "NVGS Server"),
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "NVGS-External-Watcher/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            return 200 <= response.status < 300
    except Exception as exc:
        log(f"Webhook delivery failed: {type(exc).__name__}")
        return False


def validate_configuration() -> tuple[str, ssl.SSLContext]:
    health_url = os.getenv("NVGS_REMOTE_HEALTH_URL", "").strip()
    parsed = urllib.parse.urlsplit(health_url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise SystemExit("NVGS_REMOTE_HEALTH_URL must be a complete HTTPS address.")
    if parsed.hostname in {"localhost", "127.0.0.1", "::1"}:
        raise SystemExit("Run this watcher on another device using the server LAN address.")

    ca_file = Path(os.getenv("NVGS_REMOTE_CA_FILE", "").strip())
    if not ca_file.is_file():
        raise SystemExit("NVGS_REMOTE_CA_FILE does not point to the public NVGS CA.")
    return health_url, ssl.create_default_context(cafile=ca_file)


def healthy(health_url: str, context: ssl.SSLContext, timeout: int) -> tuple[bool, str]:
    request = urllib.request.Request(
        health_url,
        headers={"User-Agent": "NVGS-External-Watcher/1.0"},
    )
    try:
        with urllib.request.urlopen(
            request,
            timeout=timeout,
            context=context,
        ) as response:
            data = json.loads(response.read(4096).decode("utf-8"))
            if response.status == 200 and data.get("status") == "ok":
                return True, "application and database are healthy"
            return False, f"health endpoint reported {data.get('status', 'unknown')}"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


def run() -> None:
    health_url, context = validate_configuration()
    interval = integer_setting("NVGS_REMOTE_INTERVAL_SECONDS", 30, 10)
    timeout = integer_setting("NVGS_REMOTE_TIMEOUT_SECONDS", 8, 2)
    failure_threshold = integer_setting("NVGS_REMOTE_FAILURE_THRESHOLD", 3, 1)
    reminder = integer_setting("NVGS_REMOTE_REMINDER_SECONDS", 1800, 300)
    server_name = os.getenv("NVGS_REMOTE_SERVER_NAME", socket.gethostname())

    consecutive_failures = 0
    known_down = False
    last_alert = 0.0
    log(f"Watching {health_url} as {server_name}.")

    while True:
        ok, detail = healthy(health_url, context, timeout)
        now = time.monotonic()
        if ok:
            consecutive_failures = 0
            if known_down:
                message = f"[RECOVERY] {server_name}: NVGS is reachable again - {detail}"
                log(message)
                send_webhook(message, "recovery")
                known_down = False
        else:
            consecutive_failures += 1
            should_alert = (
                consecutive_failures >= failure_threshold
                and (not known_down or now - last_alert >= reminder)
            )
            if should_alert:
                message = (
                    f"[WARNING] {server_name}: NVGS is unreachable from its "
                    f"external watcher - {detail}"
                )
                log(message)
                send_webhook(message, "warning")
                known_down = True
                last_alert = now
        time.sleep(interval)


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        log("External watcher stopped.")
