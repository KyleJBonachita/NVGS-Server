#!/usr/bin/env python3
"""Ubuntu desktop hub for starting NVGS services on demand."""

from __future__ import annotations

import argparse
import ipaddress
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parents[1]
DOWNLOADS_DIR = PROJECT_DIR / "download-server" / "downloads"
LOCAL_DATABASE_ADMIN_URL = "https://localhost:8443/admin/"
VIRTUAL_INTERFACE_PREFIXES = (
    "br-",
    "docker",
    "podman",
    "tailscale",
    "veth",
    "virbr",
)


@dataclass(frozen=True)
class NetworkAddress:
    interface: str
    address: str
    primary: bool = False


@dataclass(frozen=True)
class ServerDefinition:
    key: str
    name: str
    category: str
    description: str
    script: str
    scheme: str
    port: int
    path: str


@dataclass
class ServerCardWidgets:
    status: Any
    links: Any
    control_button: Any
    copy_button: Any
    open_button: Any


@dataclass(frozen=True)
class DownloadImportResult:
    copied: tuple[Path, ...]
    errors: tuple[str, ...]


def next_available_download_path(downloads_dir: Path, filename: str) -> Path:
    """Return a non-existing path without replacing an existing download."""
    candidate = downloads_dir / filename
    if not candidate.exists():
        return candidate

    original = Path(filename)
    stem = original.stem
    suffix = original.suffix
    copy_number = 2
    while True:
        candidate = downloads_dir / f"{stem} ({copy_number}){suffix}"
        if not candidate.exists():
            return candidate
        copy_number += 1


def find_download_name_conflicts(
    sources: list[Path],
    downloads_dir: Path = DOWNLOADS_DIR,
) -> tuple[str, ...]:
    """List names that already exist or occur more than once in a batch."""
    occupied_names: set[str] = set()
    try:
        occupied_names.update(
            item.name for item in downloads_dir.iterdir() if item.exists()
        )
    except OSError:
        pass

    conflicts: list[str] = []
    for source in sources:
        name = Path(source).name
        if not name or name.startswith("."):
            continue
        if name in occupied_names and name not in conflicts:
            conflicts.append(name)
        occupied_names.add(name)
    return tuple(conflicts)


def import_download_files(
    sources: list[Path],
    downloads_dir: Path = DOWNLOADS_DIR,
    conflict_policy: str = "rename",
) -> DownloadImportResult:
    """Atomically copy local files into the download library."""
    if conflict_policy not in {"rename", "replace"}:
        raise ValueError("conflict_policy must be 'rename' or 'replace'")
    downloads_dir.mkdir(parents=True, exist_ok=True)
    library_path = downloads_dir.resolve()
    copied: list[Path] = []
    errors: list[str] = []
    seen_sources: set[Path] = set()

    for untrusted_source in sources:
        source = Path(untrusted_source)
        try:
            resolved_source = source.resolve(strict=True)
        except OSError as exc:
            errors.append(f"{source.name or source}: {exc}")
            continue

        if resolved_source in seen_sources:
            continue
        seen_sources.add(resolved_source)

        if not resolved_source.is_file():
            errors.append(f"{source.name or source}: only individual files are supported")
            continue
        if source.name.startswith("."):
            errors.append(f"{source.name}: hidden files are not added")
            continue
        if resolved_source.parent == library_path:
            errors.append(f"{source.name}: already in the download library")
            continue

        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                prefix=".nvgs-upload-",
                suffix=".part",
                dir=downloads_dir,
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                with resolved_source.open("rb") as source_file:
                    shutil.copyfileobj(source_file, temporary_file, length=1024 * 1024)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())

            temporary_path.chmod(0o644)
            if conflict_policy == "replace":
                destination = downloads_dir / source.name
                # Replacement is atomic: clients see either the completed old
                # file or the completed new file, never a partial copy.
                os.replace(temporary_path, destination)
            else:
                while True:
                    destination = next_available_download_path(
                        downloads_dir,
                        source.name,
                    )
                    try:
                        # The hard link makes the completed file appear in the
                        # library in one operation, so clients never download a
                        # partially copied upload.
                        os.link(temporary_path, destination)
                        break
                    except FileExistsError:
                        continue
                temporary_path.unlink()
            temporary_path = None
            copied.append(destination)
        except OSError as exc:
            errors.append(f"{source.name}: {exc}")
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    return DownloadImportResult(tuple(copied), tuple(errors))


def count_download_files(downloads_dir: Path = DOWNLOADS_DIR) -> int:
    try:
        return sum(
            1
            for item in downloads_dir.rglob("*")
            if item.is_file() and not item.name.startswith(".")
        )
    except OSError:
        return 0


def load_gtk3_modules() -> tuple[Any, Any, Any, Any]:
    """Load matching GTK 3 modules only when the graphical app starts."""
    import gi

    gi.require_version("Gdk", "3.0")
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gdk, Gio, GLib, Gtk

    return Gdk, Gio, GLib, Gtk


def read_env_values(env_path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return values

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def parse_primary_interface(route_output: str) -> str:
    for line in route_output.splitlines():
        fields = line.split()
        if not fields or fields[0] != "default" or "dev" not in fields:
            continue
        index = fields.index("dev")
        if index + 1 < len(fields):
            return fields[index + 1]
    return ""


def physical_interface_priority(interface: str) -> int:
    lowered = interface.lower()
    if lowered.startswith(("en", "eth")):
        return 0
    if lowered.startswith(("wl", "wlan")):
        return 1
    return 2


def parse_lan_addresses(
    address_output: str,
    primary_interface: str = "",
) -> list[NetworkAddress]:
    addresses: list[NetworkAddress] = []
    seen: set[tuple[str, str]] = set()

    for line in address_output.splitlines():
        fields = line.split()
        if len(fields) < 4 or "inet" not in fields:
            continue
        interface = fields[1].removesuffix(":")
        if interface == "lo" or interface.startswith(VIRTUAL_INTERFACE_PREFIXES):
            continue
        inet_index = fields.index("inet")
        if inet_index + 1 >= len(fields):
            continue
        address_text = fields[inet_index + 1].split("/", 1)[0]
        try:
            address = ipaddress.ip_address(address_text)
        except ValueError:
            continue
        if (
            address.version != 4
            or address.is_loopback
            or address.is_link_local
            or address.is_multicast
            or address.is_unspecified
        ):
            continue
        identity = (interface, str(address))
        if identity in seen:
            continue
        seen.add(identity)
        addresses.append(
            NetworkAddress(
                interface=interface,
                address=str(address),
                primary=interface == primary_interface,
            )
        )

    return sorted(
        addresses,
        key=lambda item: (
            physical_interface_priority(item.interface),
            not item.primary,
            item.interface,
            item.address,
        ),
    )


def detect_lan_addresses() -> list[NetworkAddress]:
    try:
        route_result = subprocess.run(
            ["ip", "-4", "route", "show", "default"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
        address_result = subprocess.run(
            ["ip", "-4", "-o", "address", "show", "scope", "global"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return []

    primary_interface = parse_primary_interface(route_result.stdout)
    return parse_lan_addresses(address_result.stdout, primary_interface)


def valid_port(value: str, fallback: int) -> int:
    try:
        port = int(value)
    except (TypeError, ValueError):
        return fallback
    return port if 1 <= port <= 65535 else fallback


def build_server_catalog(env: dict[str, str]) -> tuple[ServerDefinition, ...]:
    return (
        ServerDefinition(
            key="nvgs",
            name="NVGS Server",
            category="OPERATIONS PLATFORM",
            description="Ticketing, database, alerts, and secure HTTPS access.",
            script="nvgs-session-control.sh",
            scheme="https",
            port=443,
            path="/tickets/",
        ),
        ServerDefinition(
            key="downloads",
            name="Download Server",
            category="LOCAL FILE DELIVERY",
            description="Fast local file delivery with image and cover previews.",
            script="download-session-control.sh",
            scheme="http",
            port=valid_port(env.get("DOWNLOAD_SERVER_PORT", ""), 8080),
            path="/",
        ),
    )


def preferred_nvgs_host(
    env: dict[str, str],
    addresses: list[NetworkAddress],
) -> str:
    configured_name = env.get("SERVER_ADDRESS", "").strip()
    configured_ip = env.get("SERVER_BIND_IP", "").strip()
    if configured_name and configured_name not in {"localhost", "127.0.0.1"}:
        return configured_name
    if configured_ip and configured_ip not in {"0.0.0.0", "127.0.0.1"}:
        return configured_ip
    if addresses:
        return addresses[0].address
    return "localhost"


def server_urls(
    server: ServerDefinition,
    addresses: list[NetworkAddress],
    env: dict[str, str],
) -> list[str]:
    if server.key == "nvgs":
        hosts = [preferred_nvgs_host(env, addresses)]
    else:
        hosts = []
        stable_name = env.get(
            "DOWNLOAD_SERVER_NAME",
            "download-system.local",
        ).strip()
        if stable_name:
            hosts.append(stable_name)
        hosts.extend(item.address for item in addresses)
        if not hosts:
            hosts.append("localhost")

    default_port = 443 if server.scheme == "https" else 80
    port_suffix = "" if server.port == default_port else f":{server.port}"
    return [
        f"{server.scheme}://{host}{port_suffix}{server.path}"
        for host in dict.fromkeys(hosts)
    ]


def interface_label(address: NetworkAddress) -> str:
    lowered = address.interface.lower()
    notes: list[str] = []
    if lowered.startswith(("wl", "wlan")):
        kind = "Wi-Fi"
    elif lowered.startswith(("en", "eth")):
        kind = "Ethernet"
        notes.append("server preferred")
    else:
        kind = "Network"
    if address.primary:
        notes.append("active Internet route")
    suffix = f" - {', '.join(notes)}" if notes else ""
    return f"{kind} {address.interface}: {address.address}{suffix}"


def server_is_running(
    server: ServerDefinition,
    addresses: list[NetworkAddress],
    env: dict[str, str],
) -> bool:
    if server.key == "nvgs":
        candidates = [env.get("SERVER_BIND_IP", "")]
        candidates.extend(item.address for item in addresses)
    else:
        candidates = ["127.0.0.1"]
        candidates.extend(item.address for item in addresses)

    for address in dict.fromkeys(candidate for candidate in candidates if candidate):
        if address == "0.0.0.0":
            address = "127.0.0.1"
        try:
            with socket.create_connection((address, server.port), timeout=0.08):
                return True
        except OSError:
            continue
    return False


def terminal_command(script_path: Path) -> list[str]:
    candidates = (
        ("gnome-terminal", lambda executable: [executable, "--", str(script_path)]),
        ("kgx", lambda executable: [executable, "--", str(script_path)]),
        ("x-terminal-emulator", lambda executable: [executable, "-e", str(script_path)]),
        ("konsole", lambda executable: [executable, "-e", str(script_path)]),
    )
    for name, build in candidates:
        executable = shutil.which(name)
        if executable:
            return build(executable)
    raise RuntimeError("No supported terminal application was found.")


def launch_control_script(script: str) -> None:
    script_path = PROJECT_DIR / "scripts" / script
    if not script_path.is_file():
        raise RuntimeError(f"Missing control script: {script_path.name}")
    subprocess.Popen(
        terminal_command(script_path),
        cwd=PROJECT_DIR,
        start_new_session=True,
    )


def launch_server_control(server: ServerDefinition) -> None:
    launch_control_script(server.script)


def run_gui() -> int:
    try:
        Gdk, Gio, GLib, Gtk = load_gtk3_modules()
    except (ImportError, ValueError) as exc:
        print(
            "NVGS Server Hub requires GTK 3 Python support "
            f"({type(exc).__name__}).",
            file=sys.stderr,
        )
        return 2

    css = b"""
        #server-hub-window {
            background-color: #0d100c;
            color: #f4f7ef;
        }
        headerbar {
            background-color: #151914;
            color: #f4f7ef;
            border-bottom: 1px solid #2b3228;
            box-shadow: none;
        }
        #hero-eyebrow, .card-eyebrow, .section-label {
            color: #cbed6e;
            font-size: 11px;
            font-weight: 800;
            letter-spacing: 1px;
        }
        #hub-title { font-size: 32px; font-weight: 800; }
        #hub-subtitle { color: #aab2a5; font-size: 15px; }
        #network-panel, .server-card {
            background-color: #171b16;
            border: 1px solid #30382d;
            border-radius: 14px;
        }
        #maintenance-panel {
            background-color: #171b16;
            border: 1px solid #30382d;
            border-radius: 14px;
        }
        #download-library-panel {
            background-color: #171b16;
            border: 1px solid #30382d;
            border-radius: 14px;
        }
        #download-drop-zone {
            background-color: #111510;
            border: 2px dashed #4b5845;
            border-radius: 10px;
        }
        #download-drop-zone.drag-active {
            background-color: #20291b;
            border-color: #cbed6e;
        }
        #download-drop-title { font-size: 16px; font-weight: 800; }
        #download-drop-help, #download-library-path {
            color: #aab2a5;
            font-size: 12px;
        }
        #network-panel.network-ready { border-color: #61783c; }
        #network-panel.network-wifi { border-color: #8c6640; }
        #network-panel.network-missing { border-color: #96534b; }
        #network-state { font-size: 17px; font-weight: 800; }
        #network-detail { color: #b7beb2; font-size: 13px; }
        .server-name { font-size: 22px; font-weight: 800; }
        .server-description { color: #aab2a5; font-size: 14px; }
        .server-link {
            color: #d9dfd4;
            font-family: monospace;
            font-size: 12px;
        }
        .status-running { color: #cbed6e; font-size: 11px; font-weight: 800; }
        .status-stopped { color: #929a8e; font-size: 11px; font-weight: 800; }
        button {
            background-color: #242a21;
            color: #e5e9e1;
            border: 1px solid #3b4437;
            border-radius: 7px;
            padding: 8px 12px;
        }
        button:hover { background-color: #30382c; }
        .primary-button {
            background-color: #cbed6e;
            color: #11150d;
            border-color: #cbed6e;
            font-weight: 800;
        }
        .primary-button:hover { background-color: #d9f593; }
        .warning-button { border-color: #9b7145; }
        #activity-bar {
            background-color: #121511;
            border-top: 1px solid #272e25;
        }
        #activity-label { color: #929a8e; font-size: 12px; }
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

    window = Gtk.Window(title="NVGS Server Hub")
    window.set_name("server-hub-window")
    window.set_default_size(1040, 720)
    window.set_size_request(780, 560)
    window.set_position(Gtk.WindowPosition.CENTER)
    window.set_icon_name("network-server")
    window.set_wmclass("nvgs-server-hub", "NVGS Server Hub")
    window.connect("destroy", Gtk.main_quit)

    header = Gtk.HeaderBar()
    header.set_show_close_button(True)
    header.set_title("NVGS Server Hub")
    header.set_subtitle("Local infrastructure control center")
    window.set_titlebar(header)

    root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    window.add(root)

    scroller = Gtk.ScrolledWindow()
    scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
    root.pack_start(scroller, True, True, 0)

    page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
    page.set_border_width(28)
    scroller.add(page)

    hero = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
    page.pack_start(hero, False, False, 0)

    eyebrow = Gtk.Label(label="NVGS / LOCAL INFRASTRUCTURE")
    eyebrow.set_name("hero-eyebrow")
    eyebrow.set_xalign(0)
    hero.pack_start(eyebrow, False, False, 0)

    title = Gtk.Label(label="Server control center")
    title.set_name("hub-title")
    title.set_xalign(0)
    hero.pack_start(title, False, False, 0)

    subtitle = Gtk.Label(
        label=(
            "Start, inspect, and open production services available on your "
            "Ethernet or Wi-Fi network."
        )
    )
    subtitle.set_name("hub-subtitle")
    subtitle.set_xalign(0)
    subtitle.set_line_wrap(True)
    hero.pack_start(subtitle, False, False, 0)

    network_panel = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=18)
    network_panel.set_name("network-panel")
    network_panel.set_border_width(18)
    page.pack_start(network_panel, False, False, 0)

    network_copy = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
    network_panel.pack_start(network_copy, True, True, 0)
    network_label = Gtk.Label(label="NETWORK HEALTH")
    network_label.get_style_context().add_class("section-label")
    network_label.set_xalign(0)
    network_copy.pack_start(network_label, False, False, 0)
    network_state = Gtk.Label(label="Checking connections...")
    network_state.set_name("network-state")
    network_state.set_xalign(0)
    network_copy.pack_start(network_state, False, False, 0)
    network_detail = Gtk.Label()
    network_detail.set_name("network-detail")
    network_detail.set_xalign(0)
    network_detail.set_line_wrap(True)
    network_copy.pack_start(network_detail, False, False, 0)

    network_actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    network_actions.set_valign(Gtk.Align.CENTER)
    network_panel.pack_end(network_actions, False, False, 0)
    repair_button = Gtk.Button(label="Repair / prefer Ethernet")
    repair_button.get_style_context().add_class("warning-button")
    network_actions.pack_start(repair_button, False, False, 0)
    refresh_button = Gtk.Button(label="Refresh")
    network_actions.pack_start(refresh_button, False, False, 0)

    maintenance_panel = Gtk.Box(
        orientation=Gtk.Orientation.HORIZONTAL,
        spacing=18,
    )
    maintenance_panel.set_name("maintenance-panel")
    maintenance_panel.set_border_width(18)
    page.pack_start(maintenance_panel, False, False, 0)
    maintenance_copy = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
    maintenance_panel.pack_start(maintenance_copy, True, True, 0)
    maintenance_label = Gtk.Label(label="SERVER-ONLY MAINTENANCE")
    maintenance_label.get_style_context().add_class("section-label")
    maintenance_label.set_xalign(0)
    maintenance_copy.pack_start(maintenance_label, False, False, 0)
    maintenance_title = Gtk.Label(label="Database administration")
    maintenance_title.get_style_context().add_class("server-name")
    maintenance_title.set_xalign(0)
    maintenance_copy.pack_start(maintenance_title, False, False, 0)
    maintenance_help = Gtk.Label(
        label=(
            "View and edit users, roles, tickets, and audit records. "
            "Requires the Django system-administrator password."
        )
    )
    maintenance_help.get_style_context().add_class("server-description")
    maintenance_help.set_xalign(0)
    maintenance_help.set_line_wrap(True)
    maintenance_copy.pack_start(maintenance_help, False, False, 0)
    database_admin_button = Gtk.Button(label="Open database admin")
    database_admin_button.get_style_context().add_class("warning-button")
    database_admin_button.set_valign(Gtk.Align.CENTER)
    maintenance_panel.pack_end(database_admin_button, False, False, 0)

    server_section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    page.pack_start(server_section, True, True, 0)
    server_heading = Gtk.Label(label="AVAILABLE SERVERS")
    server_heading.get_style_context().add_class("section-label")
    server_heading.set_xalign(0)
    server_section.pack_start(server_heading, False, False, 0)

    cards = Gtk.Grid()
    cards.set_column_spacing(14)
    cards.set_row_spacing(14)
    cards.set_column_homogeneous(True)
    server_section.pack_start(cards, True, True, 0)

    card_widgets: dict[str, ServerCardWidgets] = {}
    latest_urls: dict[str, list[str]] = {}
    env = read_env_values(PROJECT_DIR / ".env")
    catalog = build_server_catalog(env)

    activity_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
    activity_bar.set_name("activity-bar")
    activity_bar.set_border_width(10)
    root.pack_end(activity_bar, False, False, 0)
    activity_label = Gtk.Label(
        label="Ready. Server control terminals may be closed to stop their services."
    )
    activity_label.set_name("activity-label")
    activity_label.set_xalign(0)
    activity_bar.pack_start(activity_label, True, True, 8)

    def show_error(title: str, message: str) -> None:
        dialog = Gtk.MessageDialog(
            transient_for=window,
            flags=Gtk.DialogFlags.MODAL,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.CLOSE,
            text=title,
        )
        dialog.format_secondary_text(message)
        dialog.run()
        dialog.destroy()

    def launch_clicked(_button: object, server: ServerDefinition) -> None:
        try:
            launch_server_control(server)
            card_widgets[server.key].status.set_text("STARTING")
            activity_label.set_text(
                f"Opened {server.name} control. Keep its terminal open while in use."
            )
        except (OSError, RuntimeError) as exc:
            show_error("Could not open server control", str(exc))

    def copy_clicked(_button: object, server: ServerDefinition) -> None:
        urls = latest_urls.get(server.key, [])
        if not urls:
            return
        Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(urls[0], -1)
        activity_label.set_text(f"Copied {urls[0]}")

    def open_clicked(_button: object, server: ServerDefinition) -> None:
        urls = latest_urls.get(server.key, [])
        if not urls:
            return
        try:
            Gio.AppInfo.launch_default_for_uri(urls[0], None)
            activity_label.set_text(f"Opened {urls[0]}")
        except GLib.Error as exc:
            show_error("Could not open server address", str(exc))

    def repair_clicked(_button: object) -> None:
        try:
            launch_control_script("network-repair-control.sh")
            activity_label.set_text(
                "Opened network repair. The hub will refresh automatically."
            )
        except (OSError, RuntimeError) as exc:
            show_error("Could not open network repair", str(exc))

    def database_admin_clicked(_button: object) -> None:
        try:
            Gio.AppInfo.launch_default_for_uri(LOCAL_DATABASE_ADMIN_URL, None)
            activity_label.set_text(
                "Opened the server-only database administration login."
            )
        except GLib.Error as exc:
            show_error("Could not open database administration", str(exc))

    for index, server in enumerate(catalog):
        frame = Gtk.Frame()
        frame.get_style_context().add_class("server-card")
        frame.set_vexpand(True)
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        card.set_border_width(18)
        frame.add(card)

        card_heading = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        card.pack_start(card_heading, False, False, 0)
        category = Gtk.Label(label=server.category)
        category.get_style_context().add_class("card-eyebrow")
        category.set_xalign(0)
        card_heading.pack_start(category, True, True, 0)
        status = Gtk.Label(label="CHECKING")
        status.get_style_context().add_class("status-stopped")
        card_heading.pack_end(status, False, False, 0)

        name = Gtk.Label(label=server.name)
        name.get_style_context().add_class("server-name")
        name.set_xalign(0)
        card.pack_start(name, False, False, 0)
        description = Gtk.Label(label=server.description)
        description.get_style_context().add_class("server-description")
        description.set_xalign(0)
        description.set_line_wrap(True)
        card.pack_start(description, False, False, 0)

        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        card.pack_start(separator, False, False, 2)
        address_label = Gtk.Label(label="PRIMARY ADDRESS")
        address_label.get_style_context().add_class("section-label")
        address_label.set_xalign(0)
        card.pack_start(address_label, False, False, 0)
        links = Gtk.Label()
        links.get_style_context().add_class("server-link")
        links.set_xalign(0)
        links.set_selectable(True)
        links.set_line_wrap(True)
        card.pack_start(links, True, True, 0)

        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        card.pack_end(actions, False, False, 0)
        control_button = Gtk.Button(label="Start server")
        control_button.get_style_context().add_class("primary-button")
        control_button.connect("clicked", launch_clicked, server)
        actions.pack_start(control_button, False, False, 0)
        copy_button = Gtk.Button(label="Copy link")
        copy_button.connect("clicked", copy_clicked, server)
        actions.pack_start(copy_button, False, False, 0)
        open_button = Gtk.Button(label="Open site")
        open_button.connect("clicked", open_clicked, server)
        actions.pack_end(open_button, False, False, 0)

        card_widgets[server.key] = ServerCardWidgets(
            status=status,
            links=links,
            control_button=control_button,
            copy_button=copy_button,
            open_button=open_button,
        )
        cards.attach(frame, index % 2, index // 2, 1, 1)

    library_panel = Gtk.Frame()
    library_panel.set_name("download-library-panel")
    page.pack_start(library_panel, False, False, 0)
    library_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
    library_box.set_border_width(18)
    library_panel.add(library_box)

    library_heading_row = Gtk.Box(
        orientation=Gtk.Orientation.HORIZONTAL,
        spacing=12,
    )
    library_box.pack_start(library_heading_row, False, False, 0)
    library_heading_copy = Gtk.Box(
        orientation=Gtk.Orientation.VERTICAL,
        spacing=4,
    )
    library_heading_row.pack_start(library_heading_copy, True, True, 0)
    library_eyebrow = Gtk.Label(label="DOWNLOAD LIBRARY")
    library_eyebrow.get_style_context().add_class("section-label")
    library_eyebrow.set_xalign(0)
    library_heading_copy.pack_start(library_eyebrow, False, False, 0)
    library_title = Gtk.Label(label="Add files for local download")
    library_title.get_style_context().add_class("server-name")
    library_title.set_xalign(0)
    library_heading_copy.pack_start(library_title, False, False, 0)
    library_count = Gtk.Label()
    library_count.get_style_context().add_class("status-running")
    library_heading_row.pack_end(library_count, False, False, 0)

    library_path = Gtk.Label(label=str(DOWNLOADS_DIR))
    library_path.set_name("download-library-path")
    library_path.set_xalign(0)
    library_path.set_selectable(True)
    library_path.set_ellipsize(3)
    library_box.pack_start(library_path, False, False, 0)

    drop_zone = Gtk.EventBox()
    drop_zone.set_name("download-drop-zone")
    drop_zone.set_visible_window(True)
    library_box.pack_start(drop_zone, False, False, 0)
    drop_copy = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
    drop_copy.set_border_width(20)
    drop_zone.add(drop_copy)
    drop_title = Gtk.Label(label="Drop files here")
    drop_title.set_name("download-drop-title")
    drop_copy.pack_start(drop_title, False, False, 0)
    drop_help = Gtk.Label(
        label=(
            "Any regular file is accepted, including PNG/JPG cover images. "
            "The public website remains download-only."
        )
    )
    drop_help.set_name("download-drop-help")
    drop_help.set_line_wrap(True)
    drop_help.set_justify(Gtk.Justification.CENTER)
    drop_copy.pack_start(drop_help, False, False, 0)

    library_actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    library_box.pack_start(library_actions, False, False, 0)
    add_files_button = Gtk.Button(label="Choose files")
    add_files_button.get_style_context().add_class("primary-button")
    library_actions.pack_start(add_files_button, False, False, 0)
    open_folder_button = Gtk.Button(label="Open downloads folder")
    library_actions.pack_start(open_folder_button, False, False, 0)

    upload_in_progress = False

    def refresh_library_count() -> None:
        file_count = count_download_files()
        unit = "FILE" if file_count == 1 else "FILES"
        library_count.set_text(f"{file_count} {unit}")

    def finish_file_import(result: DownloadImportResult) -> bool:
        nonlocal upload_in_progress
        upload_in_progress = False
        add_files_button.set_sensitive(True)
        drop_zone.set_sensitive(True)
        refresh_library_count()

        copied_count = len(result.copied)
        if copied_count:
            unit = "file" if copied_count == 1 else "files"
            activity_label.set_text(
                f"Added {copied_count} {unit}. The download page updates automatically."
            )
        if result.errors:
            show_error(
                "Some files were not added",
                "\n".join(result.errors[:8]),
            )
        elif not copied_count:
            activity_label.set_text("No new files were selected.")
        return False

    def confirm_conflict_policy(paths: list[Path]) -> str | None:
        conflicts = find_download_name_conflicts(paths)
        if not conflicts:
            return "rename"

        visible_names = "\n".join(f"• {name}" for name in conflicts[:6])
        if len(conflicts) > 6:
            visible_names += f"\n• and {len(conflicts) - 6} more"
        dialog = Gtk.MessageDialog(
            transient_for=window,
            flags=Gtk.DialogFlags.MODAL,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.NONE,
            text="Some filenames already exist",
        )
        dialog.format_secondary_text(
            f"{visible_names}\n\n"
            "Replace updates the existing files. Keep both creates numbered "
            "copies such as guide (2).pdf. Your choice applies to every name "
            "listed above."
        )
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Keep both", Gtk.ResponseType.NO)
        replace_button = dialog.add_button(
            "Replace existing",
            Gtk.ResponseType.YES,
        )
        replace_button.get_style_context().add_class("destructive-action")
        dialog.set_default_response(Gtk.ResponseType.NO)
        try:
            response = dialog.run()
        finally:
            dialog.destroy()
        if response == Gtk.ResponseType.YES:
            return "replace"
        if response == Gtk.ResponseType.NO:
            return "rename"
        return None

    def import_files(paths: list[Path]) -> None:
        nonlocal upload_in_progress
        if upload_in_progress or not paths:
            return
        conflict_policy = confirm_conflict_policy(paths)
        if conflict_policy is None:
            activity_label.set_text("File upload cancelled; nothing was changed.")
            return
        upload_in_progress = True
        add_files_button.set_sensitive(False)
        drop_zone.set_sensitive(False)
        activity_label.set_text(f"Adding {len(paths)} file(s) to the library...")

        def worker() -> None:
            try:
                result = import_download_files(
                    paths,
                    conflict_policy=conflict_policy,
                )
            except OSError as exc:
                result = DownloadImportResult((), (str(exc),))
            GLib.idle_add(finish_file_import, result)

        threading.Thread(target=worker, daemon=True).start()

    def choose_files_clicked(_button: object) -> None:
        dialog = Gtk.FileChooserDialog(
            title="Add files to the NVGS download library",
            transient_for=window,
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_buttons(
            Gtk.STOCK_CANCEL,
            Gtk.ResponseType.CANCEL,
            "Add files",
            Gtk.ResponseType.ACCEPT,
        )
        dialog.set_select_multiple(True)
        try:
            if dialog.run() == Gtk.ResponseType.ACCEPT:
                import_files([Path(name) for name in dialog.get_filenames()])
        finally:
            dialog.destroy()

    def open_downloads_folder(_button: object) -> None:
        try:
            DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
            Gio.AppInfo.launch_default_for_uri(DOWNLOADS_DIR.as_uri(), None)
            activity_label.set_text("Opened the download library folder.")
        except (OSError, GLib.Error) as exc:
            show_error("Could not open the downloads folder", str(exc))

    def drag_motion(
        widget: object,
        context: object,
        _x: int,
        _y: int,
        timestamp: int,
    ) -> bool:
        widget.get_style_context().add_class("drag-active")
        Gdk.drag_status(context, Gdk.DragAction.COPY, timestamp)
        return True

    def drag_leave(widget: object, _context: object, _timestamp: int) -> None:
        widget.get_style_context().remove_class("drag-active")

    def files_dropped(
        widget: object,
        context: object,
        _x: int,
        _y: int,
        selection_data: object,
        _info: int,
        timestamp: int,
    ) -> None:
        widget.get_style_context().remove_class("drag-active")
        paths: list[Path] = []
        for uri in selection_data.get_uris() or []:
            local_path = Gio.File.new_for_uri(uri).get_path()
            if local_path:
                paths.append(Path(local_path))
        accepted = bool(paths) and not upload_in_progress
        Gtk.drag_finish(context, accepted, False, timestamp)
        if accepted:
            import_files(paths)
        elif not paths:
            show_error("Files could not be added", "Drop local files from Ubuntu Files.")

    drop_targets = [Gtk.TargetEntry.new("text/uri-list", 0, 0)]
    drop_zone.drag_dest_set(
        Gtk.DestDefaults.ALL,
        drop_targets,
        Gdk.DragAction.COPY,
    )
    drop_zone.connect("drag-motion", drag_motion)
    drop_zone.connect("drag-leave", drag_leave)
    drop_zone.connect("drag-data-received", files_dropped)
    add_files_button.connect("clicked", choose_files_clicked)
    open_folder_button.connect("clicked", open_downloads_folder)
    database_admin_button.connect("clicked", database_admin_clicked)
    refresh_library_count()

    def refresh_view(*_args: object) -> bool:
        current_env = read_env_values(PROJECT_DIR / ".env")
        addresses = detect_lan_addresses()
        current_catalog = build_server_catalog(current_env)
        refresh_library_count()
        network_context = network_panel.get_style_context()
        network_context.remove_class("network-ready")
        network_context.remove_class("network-wifi")
        network_context.remove_class("network-missing")
        if addresses:
            has_ethernet = any(
                physical_interface_priority(item.interface) == 0
                for item in addresses
            )
            if has_ethernet:
                network_state.set_text("Ethernet connected")
                network_context.add_class("network-ready")
            else:
                network_state.set_text("Wi-Fi only — Ethernet unavailable")
                network_context.add_class("network-wifi")
            network_detail.set_text("\n".join(interface_label(item) for item in addresses))
        else:
            network_state.set_text("No usable LAN address")
            network_detail.set_text(
                "Ethernet or Wi-Fi has no IPv4 address. Use Repair connection, "
                "then check the cable, modem, or Ubuntu driver if it remains missing."
            )
            network_context.add_class("network-missing")

        for server in current_catalog:
            widgets = card_widgets[server.key]
            urls = server_urls(server, addresses, current_env)
            latest_urls[server.key] = urls
            widgets.links.set_text("\n".join(urls))
            widgets.copy_button.set_sensitive(bool(urls))
            status = widgets.status
            context = status.get_style_context()
            context.remove_class("status-running")
            context.remove_class("status-stopped")
            running = server_is_running(server, addresses, current_env)
            if running:
                status.set_text("RUNNING")
                context.add_class("status-running")
                widgets.control_button.set_label("Open control")
            else:
                status.set_text("STOPPED")
                context.add_class("status-stopped")
                widgets.control_button.set_label("Start server")
            widgets.open_button.set_sensitive(running and bool(urls))
        nvgs_server = next(
            server for server in current_catalog if server.key == "nvgs"
        )
        database_admin_button.set_sensitive(
            server_is_running(nvgs_server, addresses, current_env)
        )
        return True

    refresh_button.connect("clicked", refresh_view)
    repair_button.connect("clicked", repair_clicked)
    GLib.timeout_add_seconds(3, refresh_view)
    refresh_view()

    window.show_all()
    Gtk.main()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--print-network",
        action="store_true",
        help="print detected LAN addresses without opening the GUI",
    )
    args = parser.parse_args()
    if args.print_network:
        addresses = detect_lan_addresses()
        for address in addresses:
            print(interface_label(address))
        return 0 if addresses else 1
    return run_gui()


if __name__ == "__main__":
    raise SystemExit(main())
