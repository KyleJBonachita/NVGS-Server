#!/usr/bin/env python3
"""Show trusted NVGS monitor events as one coordinated Ubuntu warning."""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import sys
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any

MAX_MESSAGE_BYTES = 8192
MAX_TITLE_LENGTH = 120
MAX_DETAIL_LENGTH = 700
MAX_VISIBLE_ALERTS = 5
BURST_DELAY_MILLISECONDS = 350
DEFAULT_DISMISS_COOLDOWN_SECONDS = 300


def load_gtk3_modules() -> tuple[Any, Any, Any]:
    """Select matching GTK 3 namespaces before PyGObject imports either one."""
    import gi

    gi.require_version("Gdk", "3.0")
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gdk, GLib, Gtk

    return Gdk, GLib, Gtk


def parse_alert(raw: bytes) -> dict[str, str] | None:
    try:
        payload: Any = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None

    if not isinstance(payload, dict):
        return None

    title = str(payload.get("title", "")).strip()[:MAX_TITLE_LENGTH]
    detail = str(payload.get("detail", "")).strip()[:MAX_DETAIL_LENGTH]
    level = str(payload.get("level", "warning")).strip().lower()
    server = str(payload.get("server", "NVGS Server")).strip()[:MAX_TITLE_LENGTH]

    if not title or not detail or level != "warning":
        return None
    return {
        "title": title,
        "detail": detail,
        "level": level,
        "server": server,
    }


def alert_identity(alert: dict[str, str]) -> str:
    """Return a stable identity so reminders update instead of stacking."""
    return alert["title"].casefold().strip()


def format_alert_batch(
    alerts: Iterable[dict[str, str]],
) -> tuple[str, str, str]:
    """Create a compact title, detail, and count for one warning screen."""
    alert_list = list(alerts)
    if not alert_list:
        return "Server warning", "No warning details were provided.", ""
    if len(alert_list) == 1:
        alert = alert_list[0]
        return alert["title"], alert["detail"], "1 active warning"

    visible = alert_list[:MAX_VISIBLE_ALERTS]
    lines = [f"• {alert['title']}: {alert['detail']}" for alert in visible]
    remaining = len(alert_list) - len(visible)
    if remaining:
        lines.append(f"• {remaining} additional warning(s) were grouped here")
    return (
        "Multiple server warnings",
        "\n".join(lines),
        f"{len(alert_list)} active warnings · one dismissal clears this group",
    )


def open_alert_socket(socket_path: Path) -> socket.socket:
    socket_path.parent.mkdir(parents=True, exist_ok=True)
    if socket_path.exists() or socket_path.is_socket():
        socket_path.unlink()

    old_umask = os.umask(0o077)
    try:
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        listener.bind(str(socket_path))
    finally:
        os.umask(old_umask)

    socket_path.chmod(0o600)
    return listener


def run_overlay(socket_path: Path) -> int:
    try:
        Gdk, GLib, Gtk = load_gtk3_modules()
    except (ImportError, ValueError) as exc:
        print(
            "Full-screen alerts require matching GDK 3 and GTK 3 libraries "
            f"({type(exc).__name__}).",
            file=sys.stderr,
            flush=True,
        )
        return 2

    listener = open_alert_socket(socket_path)
    listener.setblocking(False)
    try:
        configured_cooldown = int(
            os.getenv(
                "NVGS_ALERT_DISMISS_COOLDOWN_SECONDS",
                str(DEFAULT_DISMISS_COOLDOWN_SECONDS),
            )
        )
    except ValueError:
        configured_cooldown = DEFAULT_DISMISS_COOLDOWN_SECONDS
    dismiss_cooldown = max(30, configured_cooldown)
    cooldown_description = (
        f"{dismiss_cooldown // 60} minutes"
        if dismiss_cooldown >= 120
        else f"{dismiss_cooldown} seconds"
    )

    css = b"""
        #nvgs-alert-window {
            background: #0b0f14;
            color: #f8fafc;
        }
        #nvgs-alert-accent {
            background: #dc2626;
            min-height: 12px;
        }
        #nvgs-alert-eyebrow {
            color: #fca5a5;
            font-size: 18px;
            font-weight: 800;
        }
        #nvgs-warning-symbol {
            color: #f87171;
            font-size: 82px;
            font-weight: 900;
        }
        #nvgs-alert-title {
            color: #ffffff;
            font-size: 46px;
            font-weight: 900;
        }
        #nvgs-alert-detail {
            color: #e2e8f0;
            font-size: 26px;
            font-weight: 500;
        }
        #nvgs-alert-count {
            color: #fca5a5;
            font-size: 18px;
            font-weight: 700;
        }
        #nvgs-alert-server {
            color: #94a3b8;
            font-size: 17px;
        }
        #nvgs-alert-button {
            background: #dc2626;
            color: #ffffff;
            border: 2px solid #f87171;
            border-radius: 10px;
            font-size: 22px;
            font-weight: 800;
            padding: 16px 34px;
        }
        #nvgs-alert-button:focus {
            border-color: #ffffff;
            box-shadow: 0 0 0 3px #fca5a5;
        }
        #nvgs-alert-instruction {
            color: #94a3b8;
            font-size: 16px;
        }
    """
    provider = Gtk.CssProvider()
    provider.load_from_data(css)
    screen = Gdk.Screen.get_default()
    if screen is not None:
        Gtk.StyleContext.add_provider_for_screen(
            screen,
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    window = Gtk.Window(title="NVGS Server Warning")
    window.set_name("nvgs-alert-window")
    window.set_decorated(False)
    window.set_keep_above(True)
    window.set_modal(True)
    window.set_skip_taskbar_hint(True)
    window.set_urgency_hint(True)
    window.set_accept_focus(True)
    window.set_focus_on_map(True)
    window.set_type_hint(Gdk.WindowTypeHint.DIALOG)

    shell = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
    accent = Gtk.Box()
    accent.set_name("nvgs-alert-accent")
    shell.pack_start(accent, False, False, 0)

    content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=22)
    content.set_border_width(72)
    content.set_halign(Gtk.Align.FILL)
    content.set_valign(Gtk.Align.CENTER)

    eyebrow = Gtk.Label(label="NVGS SERVER · ACTION REQUIRED")
    eyebrow.set_name("nvgs-alert-eyebrow")
    content.pack_start(eyebrow, False, False, 0)

    symbol = Gtk.Label(label="⚠")
    symbol.set_name("nvgs-warning-symbol")
    content.pack_start(symbol, False, False, 0)

    title_label = Gtk.Label()
    title_label.set_name("nvgs-alert-title")
    title_label.set_justify(Gtk.Justification.CENTER)
    title_label.set_line_wrap(True)
    content.pack_start(title_label, False, False, 0)

    detail_label = Gtk.Label()
    detail_label.set_name("nvgs-alert-detail")
    detail_label.set_justify(Gtk.Justification.CENTER)
    detail_label.set_line_wrap(True)
    detail_label.set_max_width_chars(82)
    detail_label.set_selectable(False)
    content.pack_start(detail_label, False, False, 0)

    count_label = Gtk.Label()
    count_label.set_name("nvgs-alert-count")
    count_label.set_justify(Gtk.Justification.CENTER)
    content.pack_start(count_label, False, False, 0)

    server_label = Gtk.Label()
    server_label.set_name("nvgs-alert-server")
    server_label.set_justify(Gtk.Justification.CENTER)
    content.pack_start(server_label, False, False, 0)

    dismiss_button = Gtk.Button(label="DISMISS WARNING")
    dismiss_button.set_name("nvgs-alert-button")
    dismiss_button.set_halign(Gtk.Align.CENTER)
    content.pack_start(dismiss_button, False, False, 14)

    instruction = Gtk.Label(
        label=(
            "Press Enter or Escape · duplicate reminders pause for "
            f"{cooldown_description}"
        )
    )
    instruction.set_name("nvgs-alert-instruction")
    content.pack_start(instruction, False, False, 0)
    shell.pack_start(content, True, True, 0)
    window.add(shell)

    active_alerts: dict[str, dict[str, str]] = {}
    dismissed_until: dict[str, float] = {}
    show_timer_id: int | None = None

    def render_alerts() -> None:
        title, detail, count = format_alert_batch(active_alerts.values())
        title_label.set_text(title.upper())
        detail_label.set_text(detail)
        count_label.set_text(count)
        sources = sorted({alert["server"] for alert in active_alerts.values()})
        source_text = ", ".join(sources[:3])
        server_label.set_text(
            f"Source: {source_text or 'NVGS Server'} · {time.strftime('%H:%M:%S')}"
        )
        dismiss_button.set_label(
            "DISMISS ALL WARNINGS" if len(active_alerts) > 1 else "DISMISS WARNING"
        )

    def focus_window() -> bool:
        if not window.get_visible():
            return False
        window.set_keep_above(True)
        window.present_with_time(Gdk.CURRENT_TIME)
        dismiss_button.grab_focus()
        gdk_window = window.get_window()
        if gdk_window is not None:
            gdk_window.focus(Gdk.CURRENT_TIME)
        return False

    def show_pending() -> bool:
        nonlocal show_timer_id
        show_timer_id = None
        if not active_alerts:
            return False
        render_alerts()
        window.show_all()
        window.fullscreen()
        focus_window()
        # GTK/Wayland can map the surface after present() returns. Two short,
        # bounded retries make keyboard dismissal reliable without repeatedly
        # stealing focus after the warning has appeared.
        GLib.timeout_add(100, focus_window)
        GLib.timeout_add(300, focus_window)
        return False

    def dismiss_alerts(*_args: object) -> bool:
        nonlocal show_timer_id
        now = time.monotonic()
        for identity in active_alerts:
            dismissed_until[identity] = now + dismiss_cooldown
        active_alerts.clear()
        if show_timer_id is not None:
            GLib.source_remove(show_timer_id)
            show_timer_id = None
        window.hide()
        return True

    def key_pressed(_widget: object, event: object) -> bool:
        if event.keyval in {Gdk.KEY_Escape, Gdk.KEY_Return, Gdk.KEY_KP_Enter}:
            dismiss_alerts()
            return True
        return False

    def queue_alert(alert: dict[str, str]) -> None:
        nonlocal show_timer_id
        identity = alert_identity(alert)
        now = time.monotonic()
        if dismissed_until.get(identity, 0) > now:
            return
        dismissed_until.pop(identity, None)
        active_alerts[identity] = alert
        if window.get_visible():
            # Update the single visible warning without spawning or refocusing
            # another window. One acknowledgement will dismiss the whole burst.
            render_alerts()
        elif show_timer_id is None:
            show_timer_id = GLib.timeout_add(
                BURST_DELAY_MILLISECONDS,
                show_pending,
            )

    def socket_ready(
        _source: object,
        condition: object,
    ) -> bool:
        if condition & (GLib.IO_HUP | GLib.IO_ERR):
            return True
        while True:
            try:
                raw = listener.recv(MAX_MESSAGE_BYTES)
            except BlockingIOError:
                break
            alert = parse_alert(raw)
            if alert is not None:
                queue_alert(alert)
        return True

    dismiss_button.connect("clicked", dismiss_alerts)
    dismiss_button.connect("key-press-event", key_pressed)
    window.connect("delete-event", dismiss_alerts)
    window.connect("key-press-event", key_pressed)
    GLib.io_add_watch(
        listener.fileno(),
        GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR,
        socket_ready,
    )

    signal.signal(signal.SIGINT, lambda *_args: Gtk.main_quit())
    signal.signal(signal.SIGTERM, lambda *_args: Gtk.main_quit())

    try:
        Gtk.main()
    finally:
        listener.close()
        try:
            socket_path.unlink()
        except FileNotFoundError:
            pass
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--socket", required=True, type=Path)
    args = parser.parse_args()
    return run_overlay(args.socket)


if __name__ == "__main__":
    raise SystemExit(main())
