#!/usr/bin/env python3
"""Watch the Ubuntu journal for rejected login attempts."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time

from nvgs_alerts import log, send_alert

FAILURE_PATTERNS = [
    re.compile(r"\bfailed password\b", re.IGNORECASE),
    re.compile(r"\bauthentication failure\b", re.IGNORECASE),
    re.compile(r"\bfailed login\b", re.IGNORECASE),
    re.compile(r"\bmaximum authentication attempts exceeded\b", re.IGNORECASE),
]


def is_authentication_failure(message: str) -> bool:
    return any(pattern.search(message) for pattern in FAILURE_PATTERNS)


def summarize(message: str) -> str:
    source_match = re.search(r"\bfrom\s+([0-9a-fA-F:.]+)", message)
    user_match = re.search(
        r"\bfor\s+(?:invalid user\s+)?([^\s]+)",
        message,
        re.IGNORECASE,
    )
    pam_user_match = re.search(r"\buser=([^\s]+)", message)

    parts = []
    if user_match:
        parts.append(f"user {user_match.group(1)[:80]}")
    elif pam_user_match:
        parts.append(f"user {pam_user_match.group(1)[:80]}")
    if source_match:
        parts.append(f"source {source_match.group(1)[:80]}")
    return ", ".join(parts) if parts else "local or unidentified source"


def authentication_event_key(message: str) -> str:
    """Group retries from the same user/source even when journal text varies."""
    summary = summarize(message).casefold()
    return hashlib.sha256(summary.encode("utf-8", errors="replace")).hexdigest()


def run() -> None:
    log("NVGS authentication monitor started.")
    process = subprocess.Popen(
        ["journalctl", "--follow", "--lines", "0", "--output", "json"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    recent: dict[str, float] = {}
    dedupe_seconds = int(os.getenv("NVGS_AUTH_DEDUPE_SECONDS", "60"))

    assert process.stdout is not None
    for line in process.stdout:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        if event.get("_SYSTEMD_UNIT") == "nvgs-auth-monitor.service":
            continue
        message = str(event.get("MESSAGE", ""))
        if not is_authentication_failure(message):
            continue

        event_key = authentication_event_key(message)
        now = time.monotonic()
        if now - recent.get(event_key, 0) < dedupe_seconds:
            continue
        recent[event_key] = now

        # Do not repeat the full journal message. It may contain unnecessary
        # workstation details and would also make this service match its own log.
        send_alert(
            "Rejected login attempt",
            summarize(message),
            level="security",
        )

        if len(recent) > 1000:
            cutoff = now - dedupe_seconds
            recent = {
                key: timestamp
                for key, timestamp in recent.items()
                if timestamp >= cutoff
            }

    error_text = ""
    if process.stderr is not None:
        error_text = process.stderr.read(500).strip()
    raise RuntimeError(
        f"journalctl stopped unexpectedly: {error_text or process.returncode}"
    )


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        log("NVGS authentication monitor stopped.")
