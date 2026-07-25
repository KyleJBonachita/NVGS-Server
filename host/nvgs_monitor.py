#!/usr/bin/env python3
"""Monitor the Ubuntu laptop's basic server conditions."""

from __future__ import annotations

import glob
import json
import os
import socket
import ssl
import subprocess
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from nvgs_alerts import log, send_alert


@dataclass(frozen=True)
class CheckResult:
    healthy: bool | None
    detail: str


def read_text(path: str | Path) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except (FileNotFoundError, PermissionError, OSError):
        return None


def find_default_interface() -> str | None:
    configured = os.getenv("NVGS_NETWORK_INTERFACE", "").strip()
    if configured and configured.lower() != "auto":
        return configured
    try:
        output = subprocess.check_output(
            ["ip", "route", "show", "default"],
            text=True,
            timeout=3,
        )
        words = output.split()
        if "dev" in words:
            return words[words.index("dev") + 1]
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        pass
    return None


def check_ac_power() -> CheckResult:
    supplies = []
    for entry in glob.glob("/sys/class/power_supply/*"):
        supply_type = read_text(Path(entry) / "type")
        if supply_type in {"Mains", "USB", "USB_C", "USB_PD"}:
            supplies.append(entry)
    if not supplies:
        return CheckResult(None, "AC adapter sensor was not found")

    online_values = [read_text(Path(entry) / "online") for entry in supplies]
    if "1" in online_values:
        return CheckResult(True, "charger connected")
    return CheckResult(False, "charger unplugged or AC power unavailable")


def check_battery() -> CheckResult:
    warning_level = int(os.getenv("NVGS_BATTERY_WARNING_PERCENT", "30"))
    capacities: list[int] = []
    statuses: list[str] = []
    for entry in glob.glob("/sys/class/power_supply/*"):
        if read_text(Path(entry) / "type") != "Battery":
            continue
        capacity = read_text(Path(entry) / "capacity")
        status = read_text(Path(entry) / "status")
        if capacity and capacity.isdigit():
            capacities.append(int(capacity))
        if status:
            statuses.append(status)
    if not capacities:
        return CheckResult(None, "battery sensor was not found")

    capacity = min(capacities)
    status = ", ".join(statuses) if statuses else "unknown state"
    if capacity <= warning_level and "Charging" not in statuses:
        return CheckResult(False, f"battery at {capacity}% ({status})")
    return CheckResult(True, f"battery at {capacity}% ({status})")


def check_network_link(interface: str | None) -> CheckResult:
    if not interface:
        return CheckResult(None, "network interface was not configured or detected")
    carrier = read_text(f"/sys/class/net/{interface}/carrier")
    operational_state = read_text(f"/sys/class/net/{interface}/operstate")
    if carrier == "1":
        return CheckResult(
            True,
            f"{interface} link connected ({operational_state or 'unknown state'})",
        )
    if carrier == "0":
        return CheckResult(False, f"{interface} cable/link disconnected")
    return CheckResult(None, f"{interface} carrier sensor was unavailable")


def check_lid() -> CheckResult:
    lid_entries = glob.glob("/proc/acpi/button/lid/*/state")
    if not lid_entries:
        return CheckResult(None, "lid sensor was not found")
    state = read_text(lid_entries[0]) or ""
    if "closed" in state.lower():
        return CheckResult(False, "laptop lid is closed")
    return CheckResult(True, "laptop lid is open")


def check_internet() -> CheckResult:
    url = os.getenv(
        "NVGS_CONNECTIVITY_URL",
        "https://connectivity-check.ubuntu.com/",
    ).strip()
    if not url:
        return CheckResult(None, "Internet check is disabled")
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "NVGS-Server-Monitor/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            if 200 <= response.status < 400:
                return CheckResult(True, f"Internet reachable (HTTP {response.status})")
            return CheckResult(False, f"Internet check returned HTTP {response.status}")
    except Exception as exc:
        return CheckResult(False, f"Internet unavailable ({type(exc).__name__})")


def tcp_fallback(url: str, reason: str) -> CheckResult:
    parsed = urllib.parse.urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        with socket.create_connection((host, port), timeout=5):
            return CheckResult(
                True,
                f"application port is open; full health check skipped ({reason})",
            )
    except OSError as exc:
        return CheckResult(
            False,
            f"application port is unavailable ({type(exc).__name__})",
        )


def check_application() -> CheckResult:
    url = os.getenv(
        "NVGS_APP_HEALTH_URL",
        "https://localhost/api/health/",
    ).strip()
    ca_file = os.getenv("NVGS_CA_FILE", "").strip()
    context = None

    if url.startswith("https://"):
        if not ca_file or not Path(ca_file).is_file():
            return tcp_fallback(url, "local CA file not found")
        try:
            context = ssl.create_default_context(cafile=ca_file)
        except (OSError, ssl.SSLError) as exc:
            return tcp_fallback(url, f"CA load failed: {type(exc).__name__}")

    request = urllib.request.Request(
        url,
        headers={"User-Agent": "NVGS-Server-Monitor/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=6, context=context) as response:
            body = response.read(4096)
            data = json.loads(body.decode("utf-8"))
            if response.status == 200 and data.get("status") == "ok":
                return CheckResult(True, "application and database are healthy")
            return CheckResult(
                False,
                f"health endpoint reported {data.get('status', 'unknown')}",
            )
    except Exception as exc:
        return CheckResult(False, f"application unavailable ({type(exc).__name__})")


def run() -> None:
    interval = max(5, int(os.getenv("NVGS_CHECK_INTERVAL_SECONDS", "15")))
    reminder = max(60, int(os.getenv("NVGS_REPEAT_ALERT_SECONDS", "1800")))
    interface = find_default_interface()
    previous: dict[str, bool | None] = {}
    last_alert: dict[str, float] = {}

    log(
        "NVGS condition monitor started "
        f"(network interface: {interface or 'not detected'})."
    )

    while True:
        checks = {
            "AC power": check_ac_power(),
            "Battery": check_battery(),
            "Network link": check_network_link(interface),
            "Internet": check_internet(),
            "Application": check_application(),
            "Laptop lid": check_lid(),
        }
        now = time.monotonic()

        for name, result in checks.items():
            old_state = previous.get(name)
            previous[name] = result.healthy

            if result.healthy is None:
                if name not in last_alert:
                    log(f"INFO: {name} check unavailable - {result.detail}.")
                    last_alert[name] = now
                continue

            if result.healthy is False:
                should_alert = old_state is not False or (
                    now - last_alert.get(name, 0) >= reminder
                )
                if should_alert:
                    send_alert(name, result.detail, level="warning")
                    last_alert[name] = now
            elif old_state is False:
                send_alert(name, result.detail, level="recovery")
                last_alert[name] = now
            elif old_state is None:
                log(f"OK: {name} - {result.detail}.")

        time.sleep(interval)


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        log("NVGS condition monitor stopped.")
