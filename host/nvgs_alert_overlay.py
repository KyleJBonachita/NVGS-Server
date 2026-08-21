#!/usr/bin/env python3
"""Show trusted NVGS monitor events as one coordinated Ubuntu warning."""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import signal
import socket
import subprocess
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
ANIMATION_INTERVAL_MILLISECONDS = 80
SYSTEM_SOUND_REPEAT_SECONDS = 4.0
ASSET_DIRECTORY = Path(__file__).resolve().parent / "assets"


def load_gtk3_modules() -> tuple[Any, Any, Any, Any]:
    """Select matching GTK 3 namespaces before PyGObject imports either one."""
    import gi

    gi.require_version("Gdk", "3.0")
    gi.require_version("GdkPixbuf", "2.0")
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gdk, GdkPixbuf, GLib, Gtk

    return Gdk, GdkPixbuf, GLib, Gtk


def resolve_optional_asset(
    explicit_path: Path | None,
    environment_name: str,
    default_names: Iterable[str],
    fallback_suffixes: Iterable[str] = (),
) -> Path | None:
    """Resolve an optional user-owned alert asset without invoking a shell."""
    candidates: list[Path] = []
    if explicit_path is not None:
        candidates.append(explicit_path.expanduser())
    configured = os.getenv(environment_name, "").strip()
    if configured:
        candidates.append(Path(configured).expanduser())
    candidates.extend(ASSET_DIRECTORY / name for name in default_names)
    suffixes = {suffix.casefold() for suffix in fallback_suffixes}
    if suffixes and ASSET_DIRECTORY.is_dir():
        candidates.extend(
            sorted(
                (
                    path
                    for path in ASSET_DIRECTORY.iterdir()
                    if path.is_file() and path.suffix.casefold() in suffixes
                ),
                key=lambda path: path.name.casefold(),
            )
        )
    return next((path.resolve() for path in candidates if path.is_file()), None)


def alert_sound_commands(sound_path: Path | None) -> tuple[list[list[str]], bool]:
    """Return safe audio-player fallbacks and whether they play custom media."""
    commands: list[list[str]] = []
    if sound_path is not None:
        canberra = shutil.which("canberra-gtk-play")
        if canberra:
            commands.append(
                [
                    canberra,
                    f"--file={sound_path}",
                    "--description=NVGS server warning",
                ]
            )
        gsound = shutil.which("gsound-play")
        if gsound:
            commands.append([gsound, f"--file={sound_path}"])
        gst_launch = shutil.which("gst-launch-1.0")
        if gst_launch:
            commands.append(
                [gst_launch, "-q", "playbin", f"uri={sound_path.as_uri()}"]
            )
        paplay = shutil.which("paplay")
        if paplay:
            commands.append([paplay, str(sound_path)])
        ffplay = shutil.which("ffplay")
        if ffplay:
            commands.append(
                [
                    ffplay,
                    "-nodisp",
                    "-autoexit",
                    "-loglevel",
                    "quiet",
                    str(sound_path),
                ]
            )
        return commands, True

    canberra = shutil.which("canberra-gtk-play")
    if canberra:
        commands.append(
            [
                canberra,
                "--id=dialog-warning",
                "--description=NVGS server warning",
            ]
        )

    default_sound = Path("/usr/share/sounds/freedesktop/stereo/dialog-warning.oga")
    paplay = shutil.which("paplay")
    if paplay and default_sound.is_file():
        commands.append([paplay, str(default_sound)])
    return commands, False


def primary_monitor_size(gdk: Any) -> tuple[int, int] | None:
    """Return the active display size through GTK's non-deprecated monitor API."""
    display = gdk.Display.get_default()
    if display is None:
        return None
    monitor = display.get_primary_monitor()
    if monitor is None and display.get_n_monitors() > 0:
        monitor = display.get_monitor(0)
    if monitor is None:
        return None
    geometry = monitor.get_geometry()
    return max(1, geometry.width), max(1, geometry.height)


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


def run_overlay(
    socket_path: Path,
    background_path: Path | None = None,
    sound_path: Path | None = None,
) -> int:
    try:
        Gdk, GdkPixbuf, GLib, Gtk = load_gtk3_modules()
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
            background: #52070c;
            color: #f8fafc;
        }
        #nvgs-alert-card {
            background: rgba(8, 11, 16, 0.90);
            border: 2px solid rgba(254, 202, 202, 0.72);
            border-radius: 18px;
        }
        #nvgs-alert-card-media {
            background: rgba(8, 11, 16, 0.76);
            border: 2px solid rgba(255, 255, 255, 0.72);
            border-radius: 18px;
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
        #nvgs-sound-button {
            background: rgba(30, 41, 59, 0.92);
            color: #f8fafc;
            border: 1px solid #94a3b8;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 700;
            padding: 9px 18px;
        }
        #nvgs-sound-button:focus {
            border-color: #ffffff;
        }
        #nvgs-alert-instruction {
            color: #cbd5e1;
            font-size: 16px;
        }
    """
    provider = Gtk.CssProvider()
    provider.load_from_data(css)
    screen = Gdk.Screen.get_default()
    monitor_size = primary_monitor_size(Gdk)
    if screen is not None:
        Gtk.StyleContext.add_provider_for_screen(
            screen,
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    window = Gtk.Window(title="NVGS Server Warning")
    window.set_name("nvgs-alert-window")
    window.set_decorated(False)
    window.set_resizable(True)
    window.set_keep_above(True)
    window.set_skip_taskbar_hint(True)
    window.set_skip_pager_hint(True)
    window.set_urgency_hint(True)
    window.set_accept_focus(True)
    window.set_focus_on_map(True)
    window.stick()
    if monitor_size is not None:
        window.set_default_size(*monitor_size)

    stage = Gtk.Overlay()
    stage.set_hexpand(True)
    stage.set_vexpand(True)

    background = Gtk.DrawingArea()
    background.set_hexpand(True)
    background.set_vexpand(True)
    stage.add(background)

    shell = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
    shell.set_name("nvgs-alert-card")
    shell.set_halign(Gtk.Align.CENTER)
    shell.set_valign(Gtk.Align.CENTER)
    shell.set_margin_start(32)
    shell.set_margin_end(32)
    shell.set_margin_top(32)
    shell.set_margin_bottom(32)
    card_width = 940
    if monitor_size is not None:
        card_width = min(card_width, max(420, monitor_size[0] - 96))
    shell.set_size_request(card_width, -1)
    accent = Gtk.Box()
    accent.set_name("nvgs-alert-accent")
    shell.pack_start(accent, False, False, 0)

    content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=22)
    content.set_border_width(48)
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

    sound_button = Gtk.Button(label="MUTE SOUND")
    sound_button.set_name("nvgs-sound-button")
    sound_button.set_halign(Gtk.Align.CENTER)
    content.pack_start(sound_button, False, False, 0)

    instruction = Gtk.Label(
        label=(
            "Enter/Escape: dismiss  |  M: mute sound  |  reminders pause for "
            f"{cooldown_description}"
        )
    )
    instruction.set_name("nvgs-alert-instruction")
    content.pack_start(instruction, False, False, 0)
    shell.pack_start(content, True, True, 0)
    stage.add_overlay(shell)
    window.add(stage)

    resolved_background = resolve_optional_asset(
        background_path,
        "NVGS_ALERT_BACKGROUND_GIF",
        ("nvgs-alert-background.gif",),
        (".gif",),
    )
    resolved_sound = resolve_optional_asset(
        sound_path,
        "NVGS_ALERT_SOUND_FILE",
        (
            "nvgs-alert-sound.oga",
            "nvgs-alert-sound.ogg",
            "nvgs-alert-sound.wav",
            "nvgs-alert-sound.mp3",
        ),
        (".oga", ".ogg", ".wav", ".mp3"),
    )
    media_animation: Any | None = None
    media_iterator: Any | None = None
    if resolved_background is not None:
        shell.set_name("nvgs-alert-card-media")
        try:
            media_animation = GdkPixbuf.PixbufAnimation.new_from_file(
                str(resolved_background)
            )
            media_iterator = media_animation.get_iter(None)
        except Exception as exc:  # GTK reports malformed local media at runtime.
            print(
                f"Could not load alert GIF {resolved_background}: {exc}",
                file=sys.stderr,
                flush=True,
            )
            media_animation = None
            media_iterator = None

    animation_started = time.monotonic()

    def draw_background(area: object, context: object) -> bool:
        width = max(1, area.get_allocated_width())
        height = max(1, area.get_allocated_height())
        elapsed = time.monotonic() - animation_started

        if media_iterator is not None:
            context.set_source_rgb(0.0, 0.0, 0.0)
            context.paint()
            media_iterator.advance(None)
            frame = media_iterator.get_pixbuf()
            frame_width = max(1, frame.get_width())
            frame_height = max(1, frame.get_height())
            scale = max(width / frame_width, height / frame_height)
            scaled_width = max(1, math.ceil(frame_width * scale))
            scaled_height = max(1, math.ceil(frame_height * scale))
            scaled = frame.scale_simple(
                scaled_width,
                scaled_height,
                GdkPixbuf.InterpType.BILINEAR,
            )
            x_offset = (width - scaled_width) / 2
            y_offset = (height - scaled_height) / 2
            Gdk.cairo_set_source_pixbuf(context, scaled, x_offset, y_offset)
            context.paint()
            return False

        pulse = (math.sin(elapsed * 2.2) + 1.0) / 2.0
        context.set_source_rgb(0.25 + pulse * 0.10, 0.015, 0.03)
        context.paint()

        band_spacing = 260
        band_width = 86
        offset = (elapsed * 72) % band_spacing
        context.set_source_rgba(1.0, 0.18, 0.14, 0.11)
        band_x = -height - band_spacing + offset
        while band_x < width + band_spacing:
            context.move_to(band_x, 0)
            context.line_to(band_x + band_width, 0)
            context.line_to(band_x + height + band_width, height)
            context.line_to(band_x + height, height)
            context.close_path()
            context.fill()
            band_x += band_spacing

        ring_pulse = (math.sin(elapsed * 2.6) + 1.0) / 2.0
        context.set_line_width(3.0)
        for index in range(4):
            radius = 150 + index * 110 + ring_pulse * 34
            context.set_source_rgba(1.0, 0.55, 0.50, 0.16 - index * 0.025)
            context.arc(width / 2, height / 2, radius, 0, math.tau)
            context.stroke()
        return False

    def animate_background() -> bool:
        if window.get_visible():
            background.queue_draw()
        return True

    background.connect("draw", draw_background)
    GLib.timeout_add(ANIMATION_INTERVAL_MILLISECONDS, animate_background)

    active_alerts: dict[str, dict[str, str]] = {}
    dismissed_until: dict[str, float] = {}
    show_timer_id: int | None = None
    sound_timer_id: int | None = None
    sound_process: subprocess.Popen[bytes] | None = None
    sound_enabled = True
    last_system_sound_started = 0.0
    sound_commands, custom_sound = alert_sound_commands(resolved_sound)
    sound_command_index = 0
    consecutive_sound_failures = 0
    sound_failed = False
    if resolved_background is not None:
        print(
            f"Custom alert GIF: {resolved_background}",
            flush=True,
        )
    if resolved_sound is not None:
        print(
            f"Custom alert sound: {resolved_sound} "
            f"({len(sound_commands)} installed player option(s))",
            flush=True,
        )
        if not sound_commands:
            print(
                "No supported command-line audio player was found; "
                "the custom sound cannot play.",
                file=sys.stderr,
                flush=True,
            )

    def update_sound_button() -> None:
        if not sound_commands:
            sound_button.set_label("SOUND UNAVAILABLE")
            sound_button.set_sensitive(False)
        elif sound_failed:
            sound_button.set_label("SOUND FAILED - RETRY")
            sound_button.set_sensitive(True)
        elif sound_enabled:
            sound_button.set_label("MUTE SOUND")
            sound_button.set_sensitive(True)
        else:
            sound_button.set_label("SOUND MUTED - ENABLE")
            sound_button.set_sensitive(True)

    def stop_sound_loop() -> None:
        nonlocal sound_timer_id, sound_process
        if sound_timer_id is not None:
            GLib.source_remove(sound_timer_id)
            sound_timer_id = None
        if sound_process is not None and sound_process.poll() is None:
            sound_process.terminate()
        sound_process = None

    def play_sound_once() -> None:
        nonlocal consecutive_sound_failures, last_system_sound_started
        nonlocal sound_command_index, sound_enabled, sound_failed, sound_process
        if not sound_enabled or not sound_commands:
            return
        if sound_process is not None:
            return_code = sound_process.poll()
            if return_code is None:
                return
            failed_command = sound_commands[sound_command_index]
            sound_process = None
            if return_code != 0:
                consecutive_sound_failures += 1
                print(
                    f"Alert audio player {Path(failed_command[0]).name} failed "
                    f"with status {return_code}; trying another player.",
                    file=sys.stderr,
                    flush=True,
                )
                if consecutive_sound_failures >= len(sound_commands):
                    sound_failed = True
                    sound_enabled = False
                    update_sound_button()
                    return
                sound_command_index = (sound_command_index + 1) % len(sound_commands)
            else:
                consecutive_sound_failures = 0
        now = time.monotonic()
        if (
            not custom_sound
            and now - last_system_sound_started < SYSTEM_SOUND_REPEAT_SECONDS
        ):
            return
        try:
            sound_process = subprocess.Popen(
                sound_commands[sound_command_index],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            last_system_sound_started = now
        except OSError as exc:
            print(f"Could not play the alert sound: {exc}", file=sys.stderr, flush=True)

    def sound_loop_tick() -> bool:
        nonlocal sound_timer_id
        play_sound_once()
        if sound_failed:
            sound_timer_id = None
            return False
        return True

    def start_sound_loop() -> None:
        nonlocal sound_timer_id
        stop_sound_loop()
        if sound_enabled and sound_commands:
            play_sound_once()
            sound_timer_id = GLib.timeout_add(500, sound_loop_tick)

    def toggle_sound(*_args: object) -> bool:
        nonlocal consecutive_sound_failures, sound_command_index
        nonlocal sound_enabled, sound_failed
        if not sound_commands:
            return True
        if sound_failed:
            sound_command_index = 0
            consecutive_sound_failures = 0
            sound_failed = False
            sound_enabled = True
        else:
            sound_enabled = not sound_enabled
        if sound_enabled:
            start_sound_loop()
        else:
            stop_sound_loop()
        update_sound_button()
        return True

    update_sound_button()

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

    def mapped_fullscreen(_widget: object, _event: object) -> bool:
        # Reassert after mapping for compositors that ignored the pre-map call.
        window.fullscreen()
        GLib.idle_add(focus_window)
        return False

    def show_pending() -> bool:
        nonlocal show_timer_id
        show_timer_id = None
        if not active_alerts:
            return False
        render_alerts()
        if monitor_size is not None:
            window.resize(*monitor_size)
        window.fullscreen()
        window.show_all()
        start_sound_loop()
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
        stop_sound_loop()
        window.hide()
        return True

    def key_pressed(_widget: object, event: object) -> bool:
        if event.keyval in {Gdk.KEY_Escape, Gdk.KEY_Return, Gdk.KEY_KP_Enter}:
            dismiss_alerts()
            return True
        if event.keyval in {Gdk.KEY_m, Gdk.KEY_M}:
            toggle_sound()
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
    sound_button.connect("clicked", toggle_sound)
    sound_button.connect("key-press-event", key_pressed)
    window.connect("delete-event", dismiss_alerts)
    window.connect("map-event", mapped_fullscreen)
    window.connect("key-press-event", key_pressed)
    GLib.io_add_watch(
        listener.fileno(),
        GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR,
        socket_ready,
    )

    def quit_overlay(*_args: object) -> None:
        stop_sound_loop()
        Gtk.main_quit()

    signal.signal(signal.SIGINT, quit_overlay)
    signal.signal(signal.SIGTERM, quit_overlay)

    try:
        Gtk.main()
    finally:
        stop_sound_loop()
        listener.close()
        try:
            socket_path.unlink()
        except FileNotFoundError:
            pass
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--socket", required=True, type=Path)
    parser.add_argument("--background", type=Path)
    parser.add_argument("--sound-file", type=Path)
    args = parser.parse_args()
    return run_overlay(args.socket, args.background, args.sound_file)


if __name__ == "__main__":
    raise SystemExit(main())
