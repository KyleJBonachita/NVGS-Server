#!/usr/bin/env python3
"""Ubuntu desktop hub for starting NVGS services on demand."""

from __future__ import annotations

import argparse
import ipaddress
import shutil
import socket
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_DIR = Path(__file__).resolve().parents[1]
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

    def refresh_view(*_args: object) -> bool:
        current_env = read_env_values(PROJECT_DIR / ".env")
        addresses = detect_lan_addresses()
        current_catalog = build_server_catalog(current_env)
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
