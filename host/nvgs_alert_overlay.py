#!/usr/bin/env python3
"""Show trusted NVGS monitor events as a full-screen Ubuntu warning."""

from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import sys
from pathlib import Path
from typing import Any

MAX_MESSAGE_BYTES = 8192
MAX_TITLE_LENGTH = 120
MAX_DETAIL_LENGTH = 700


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

    css = b"""
        #nvgs-alert-window {
            background: #8b1010;
            color: #ffffff;
        }
        #nvgs-warning-symbol {
            font-size: 96px;
            font-weight: 900;
        }
        #nvgs-alert-title {
            font-size: 52px;
            font-weight: 900;
        }
        #nvgs-alert-detail {
            font-size: 30px;
            font-weight: 600;
        }
        #nvgs-alert-server {
            font-size: 20px;
        }
        #nvgs-alert-button {
            font-size: 24px;
            font-weight: 700;
            padding: 18px 36px;
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

    content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=28)
    content.set_border_width(70)
    content.set_halign(Gtk.Align.FILL)
    content.set_valign(Gtk.Align.CENTER)

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
    detail_label.set_max_width_chars(70)
    content.pack_start(detail_label, False, False, 0)

    server_label = Gtk.Label()
    server_label.set_name("nvgs-alert-server")
    server_label.set_justify(Gtk.Justification.CENTER)
    content.pack_start(server_label, False, False, 0)

    dismiss_button = Gtk.Button(label="I UNDERSTAND — DISMISS WARNING")
    dismiss_button.set_name("nvgs-alert-button")
    dismiss_button.set_halign(Gtk.Align.CENTER)
    dismiss_button.connect("clicked", lambda _button: window.hide())
    content.pack_start(dismiss_button, False, False, 18)

    instruction = Gtk.Label(label="Press Enter or Escape to dismiss")
    content.pack_start(instruction, False, False, 0)
    window.add(content)

    def hide_window(*_args: object) -> bool:
        window.hide()
        return True

    def key_pressed(_window: object, event: object) -> bool:
        if event.keyval in {Gdk.KEY_Escape, Gdk.KEY_Return, Gdk.KEY_KP_Enter}:
            window.hide()
            return True
        return False

    def show_alert(alert: dict[str, str]) -> None:
        title_label.set_text(alert["title"].upper())
        detail_label.set_text(alert["detail"])
        server_label.set_text(f"Source: {alert['server']}")
        window.show_all()
        window.fullscreen()
        window.present()
        dismiss_button.grab_focus()

    def socket_ready(
        _source: object,
        condition: object,
    ) -> bool:
        if condition & (GLib.IO_HUP | GLib.IO_ERR):
            return True
        try:
            raw = listener.recv(MAX_MESSAGE_BYTES)
        except BlockingIOError:
            return True
        alert = parse_alert(raw)
        if alert is not None:
            show_alert(alert)
        return True

    window.connect("delete-event", hide_window)
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
