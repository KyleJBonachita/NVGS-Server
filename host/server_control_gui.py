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
    description: str
    script: str
    scheme: str
    port: int
    path: str


def load_gtk3_modules() -> tuple[Any, Any, Any]:
    """Load matching GTK 3 modules only when the graphical app starts."""
    import gi

    gi.require_version("Gdk", "3.0")
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gdk, GLib, Gtk

    return Gdk, GLib, Gtk


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
        key=lambda item: (not item.primary, item.interface, item.address),
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
            description="Ticketing, database, alerts, and secure HTTPS access.",
            script="nvgs-session-control.sh",
            scheme="https",
            port=443,
            path="/tickets/",
        ),
        ServerDefinition(
            key="downloads",
            name="Download Server",
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
        stable_name = env.get("NVGS_LAN_SERVER_NAME", "").strip()
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
    if lowered.startswith(("wl", "wlan")):
        kind = "Wi-Fi"
    elif lowered.startswith(("en", "eth")):
        kind = "Ethernet"
    else:
        kind = "Network"
    primary = " - active route" if address.primary else ""
    return f"{kind} {address.interface}: {address.address}{primary}"


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


def launch_server_control(server: ServerDefinition) -> None:
    script_path = PROJECT_DIR / "scripts" / server.script
    if not script_path.is_file():
        raise RuntimeError(f"Missing control script: {script_path.name}")
    subprocess.Popen(
        terminal_command(script_path),
        cwd=PROJECT_DIR,
        start_new_session=True,
    )


def run_gui() -> int:
    try:
        Gdk, GLib, Gtk = load_gtk3_modules()
    except (ImportError, ValueError) as exc:
        print(
            "NVGS Server Hub requires GTK 3 Python support "
            f"({type(exc).__name__}).",
            file=sys.stderr,
        )
        return 2

    css = b"""
        #server-hub-window { background: #10130f; color: #f3f5ef; }
        #hub-title { font-size: 30px; font-weight: 800; }
        #hub-subtitle { color: #a8afa3; font-size: 15px; }
        #network-panel, .server-card {
            background: #191d17;
            border: 1px solid #30372d;
            border-radius: 14px;
        }
        #network-title { color: #d6ff65; font-size: 13px; font-weight: 800; }
        #network-detail { color: #b6bdb1; }
        .server-name { font-size: 21px; font-weight: 800; }
        .server-description { color: #a8afa3; font-size: 14px; }
        .server-link { color: #c7cfbf; font-family: monospace; font-size: 12px; }
        .status-running { color: #d6ff65; font-weight: 800; }
        .status-stopped { color: #a8afa3; font-weight: 700; }
        .launch-button {
            background: #d6ff65;
            color: #12160d;
            border: 0;
            border-radius: 8px;
            padding: 11px 18px;
            font-weight: 800;
        }
        .launch-button:hover { background: #e1ff8d; }
        #footer-note { color: #8e9689; font-size: 12px; }
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
    window.set_default_size(820, 620)
    window.set_position(Gtk.WindowPosition.CENTER)
    window.set_icon_name("network-server")
    window.set_wmclass("nvgs-server-hub", "NVGS Server Hub")
    window.connect("destroy", Gtk.main_quit)

    page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
    page.set_border_width(28)
    window.add(page)

    title = Gtk.Label(label="Server Hub")
    title.set_name("hub-title")
    title.set_xalign(0)
    page.pack_start(title, False, False, 0)

    subtitle = Gtk.Label(
        label="Choose a local server. Each one opens in its own control terminal."
    )
    subtitle.set_name("hub-subtitle")
    subtitle.set_xalign(0)
    page.pack_start(subtitle, False, False, 0)

    network_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=7)
    network_panel.set_name("network-panel")
    network_panel.set_border_width(16)
    page.pack_start(network_panel, False, False, 0)

    network_heading_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    network_panel.pack_start(network_heading_row, False, False, 0)
    network_title = Gtk.Label(label="DETECTED LOCAL NETWORK")
    network_title.set_name("network-title")
    network_title.set_xalign(0)
    network_heading_row.pack_start(network_title, True, True, 0)
    refresh_button = Gtk.Button(label="Refresh")
    network_heading_row.pack_end(refresh_button, False, False, 0)

    network_detail = Gtk.Label()
    network_detail.set_name("network-detail")
    network_detail.set_xalign(0)
    network_detail.set_line_wrap(True)
    network_panel.pack_start(network_detail, False, False, 0)

    cards = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
    page.pack_start(cards, True, True, 0)

    status_labels: dict[str, Any] = {}
    link_labels: dict[str, Any] = {}
    env = read_env_values(PROJECT_DIR / ".env")
    catalog = build_server_catalog(env)

    def show_error(message: str) -> None:
        dialog = Gtk.MessageDialog(
            transient_for=window,
            flags=Gtk.DialogFlags.MODAL,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.CLOSE,
            text="Could not open server control",
        )
        dialog.format_secondary_text(message)
        dialog.run()
        dialog.destroy()

    def launch_clicked(_button: object, server: ServerDefinition) -> None:
        try:
            launch_server_control(server)
            status_labels[server.key].set_text("CONTROL TERMINAL OPENED")
        except (OSError, RuntimeError) as exc:
            show_error(str(exc))

    for server in catalog:
        frame = Gtk.Frame()
        frame.get_style_context().add_class("server-card")
        card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
        card.set_border_width(18)
        frame.add(card)

        copy = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=7)
        card.pack_start(copy, True, True, 0)
        name = Gtk.Label(label=server.name)
        name.get_style_context().add_class("server-name")
        name.set_xalign(0)
        copy.pack_start(name, False, False, 0)
        description = Gtk.Label(label=server.description)
        description.get_style_context().add_class("server-description")
        description.set_xalign(0)
        description.set_line_wrap(True)
        copy.pack_start(description, False, False, 0)
        links = Gtk.Label()
        links.get_style_context().add_class("server-link")
        links.set_xalign(0)
        links.set_selectable(True)
        links.set_line_wrap(True)
        copy.pack_start(links, False, False, 3)
        link_labels[server.key] = links

        actions = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        actions.set_valign(Gtk.Align.CENTER)
        card.pack_end(actions, False, False, 0)
        status = Gtk.Label(label="CHECKING")
        actions.pack_start(status, False, False, 0)
        status_labels[server.key] = status
        launch_button = Gtk.Button(label="Open control")
        launch_button.get_style_context().add_class("launch-button")
        launch_button.connect("clicked", launch_clicked, server)
        actions.pack_start(launch_button, False, False, 0)
        cards.pack_start(frame, False, False, 0)

    footer = Gtk.Label(
        label=(
            "Keep a server's control terminal open while it is needed. "
            "DownloadServer uses every active LAN address; NVGS follows the active "
            "adapter when dynamic LAN mode is enabled. Ethernet and Wi-Fi clients "
            "must share a LAN without client isolation."
        )
    )
    footer.set_name("footer-note")
    footer.set_xalign(0)
    footer.set_line_wrap(True)
    page.pack_end(footer, False, False, 0)

    def refresh_view(*_args: object) -> bool:
        current_env = read_env_values(PROJECT_DIR / ".env")
        addresses = detect_lan_addresses()
        current_catalog = build_server_catalog(current_env)
        if addresses:
            network_detail.set_text("\n".join(interface_label(item) for item in addresses))
        else:
            network_detail.set_text(
                "No active Ethernet or Wi-Fi IPv4 address detected. Connect to a LAN and refresh."
            )

        for server in current_catalog:
            link_labels[server.key].set_text(
                "\n".join(server_urls(server, addresses, current_env))
            )
            status = status_labels[server.key]
            context = status.get_style_context()
            context.remove_class("status-running")
            context.remove_class("status-stopped")
            if server_is_running(server, addresses, current_env):
                status.set_text("RUNNING")
                context.add_class("status-running")
            else:
                status.set_text("STOPPED")
                context.add_class("status-stopped")
        return True

    refresh_button.connect("clicked", refresh_view)
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
