#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
    echo "Run this setup with sudo:" >&2
    echo "  sudo ./scripts/install-app-controlled-mode.sh" >&2
    exit 1
fi

refresh_only=false
if [[ "${1:-}" == "--refresh" ]]; then
    refresh_only=true
elif [[ -n "${1:-}" ]]; then
    echo "Unknown option: $1" >&2
    exit 1
fi

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

if [[ ! -d /etc/systemd/system ]]; then
    echo "This script must be run on an Ubuntu system using systemd." >&2
    exit 1
fi

if [[ ! -f .env ]]; then
    echo "Missing .env. Run ./scripts/bootstrap-secrets.sh first." >&2
    exit 1
fi
env_owner="$(stat -c '%u:%g' .env)"

desktop_user="${SUDO_USER:-}"
if [[ -z "$desktop_user" || "$desktop_user" == "root" ]]; then
    echo "Could not identify the Ubuntu desktop user." >&2
    echo "Run this from your normal account using sudo, not from a root login." >&2
    exit 1
fi

desktop_home="$(getent passwd "$desktop_user" | cut -d: -f6)"
if [[ -z "$desktop_home" || ! -d "$desktop_home" ]]; then
    echo "Could not find the home folder for $desktop_user." >&2
    exit 1
fi
desktop_group="$(id -gn "$desktop_user")"

server_address="$(
    sed -n 's/^[[:space:]]*SERVER_ADDRESS[[:space:]]*=[[:space:]]*//p' .env \
        | tail -n 1 \
        | tr -d '\r'
)"
server_address="${server_address:-localhost}"
if [[ ! "$server_address" =~ ^[A-Za-z0-9._:-]+$ ]]; then
    echo "SERVER_ADDRESS contains unsupported characters: $server_address" >&2
    exit 1
fi

escaped_project_dir="${project_dir//\\/\\\\}"
escaped_project_dir="${escaped_project_dir//&/\\&}"
escaped_project_dir="${escaped_project_dir//|/\\|}"

for service in nvgs-monitor.service nvgs-auth-monitor.service; do
    sed "s|__PROJECT_DIR__|${escaped_project_dir}|g" \
        "host/systemd/${service}" > "/etc/systemd/system/${service}"
    chmod 0644 "/etc/systemd/system/${service}"
done

if [[ ! -f /etc/nvgs-monitor.env ]]; then
    default_interface="$(
        ip route show default 2>/dev/null \
            | awk '/default/ {for (i=1; i<=NF; i++) if ($i=="dev") {print $(i+1); exit}}'
    )"
    default_interface="${default_interface:-auto}"

    {
        echo "NVGS_SERVER_NAME=NVGS-Server"
        echo "NVGS_NETWORK_INTERFACE=${default_interface}"
        echo "NVGS_APP_HEALTH_URL=https://${server_address}/api/health/"
        echo "NVGS_CA_FILE=${project_dir}/nvgs-local-ca.crt"
        echo "NVGS_CONNECTIVITY_URL=https://connectivity-check.ubuntu.com/"
        echo "NVGS_CHECK_INTERVAL_SECONDS=15"
        echo "NVGS_REPEAT_ALERT_SECONDS=1800"
        echo "NVGS_BATTERY_WARNING_PERCENT=30"
        echo "NVGS_AUTH_DEDUPE_SECONDS=60"
        echo "NVGS_ALERT_WEBHOOK_URL="
    } > /etc/nvgs-monitor.env
else
    sed -i \
        "s|^NVGS_APP_HEALTH_URL=.*|NVGS_APP_HEALTH_URL=https://${server_address}/api/health/|" \
        /etc/nvgs-monitor.env
    sed -i \
        "s|^NVGS_CA_FILE=.*|NVGS_CA_FILE=${escaped_project_dir}/nvgs-local-ca.crt|" \
        /etc/nvgs-monitor.env
fi

set_monitor_env_value() {
    local key="$1"
    local value="$2"

    if grep -q "^[[:space:]]*${key}[[:space:]]*=" /etc/nvgs-monitor.env; then
        sed -i \
            "s|^[[:space:]]*${key}[[:space:]]*=.*|${key}=${value}|" \
            /etc/nvgs-monitor.env
    else
        printf '%s=%s\n' "$key" "$value" >> /etc/nvgs-monitor.env
    fi
}

set_monitor_env_value "NVGS_DESKTOP_NOTIFICATIONS" "true"
set_monitor_env_value "NVGS_DESKTOP_USER" "$desktop_user"
set_monitor_env_value "NVGS_FULLSCREEN_ALERTS" "true"
set_monitor_env_value "NVGS_CHECK_INTERVAL_SECONDS" "5"
chmod 0600 /etc/nvgs-monitor.env

if ! command -v notify-send >/dev/null 2>&1; then
    echo "WARNING: notify-send is missing, so desktop popups cannot appear." >&2
    echo "Install it with: sudo apt install libnotify-bin" >&2
fi
if ! python3 -c \
    'import gi; gi.require_version("Gdk", "3.0"); gi.require_version("GdkPixbuf", "2.0"); gi.require_version("Gtk", "3.0"); from gi.repository import Gdk, GdkPixbuf, Gtk' \
    >/dev/null 2>&1; then
    echo "WARNING: Matching GDK/GTK 3 Python support is unavailable." >&2
    echo "Full-screen alerts cannot appear." >&2
    echo "Install it with:" >&2
    echo "  sudo apt install python3-gi gir1.2-gtk-3.0" >&2
fi
if ! command -v gnome-terminal >/dev/null 2>&1 \
    && ! command -v kgx >/dev/null 2>&1 \
    && ! command -v x-terminal-emulator >/dev/null 2>&1 \
    && ! command -v konsole >/dev/null 2>&1; then
    echo "WARNING: No supported terminal application was found." >&2
    echo "The Server Hub opens each selected server in a control terminal." >&2
fi

set_env_value() {
    local key="$1"
    local value="$2"

    if grep -q "^[[:space:]]*${key}[[:space:]]*=" .env; then
        sed -i "s|^[[:space:]]*${key}[[:space:]]*=.*|${key}=${value}|" .env
    else
        printf '\n%s=%s\n' "$key" "$value" >> .env
    fi
}

echo "Switching NVGS from always-on mode to app-controlled mode..."
set_env_value "NVGS_HOST_MODE" "on_demand"
set_env_value "NVGS_RESTART_POLICY" "no"
chown "$env_owner" .env

if [[ "$refresh_only" == "true" ]]; then
    systemctl disable nvgs-monitor.service nvgs-auth-monitor.service \
        >/dev/null 2>&1 || true
else
    systemctl disable --now nvgs-monitor.service nvgs-auth-monitor.service \
        >/dev/null 2>&1 || true
fi
systemctl unmask sleep.target suspend.target hibernate.target \
    hybrid-sleep.target >/dev/null 2>&1 || true

logind_config="/etc/systemd/logind.conf.d/50-nvgs-server.conf"
disabled_logind_config="${logind_config}.disabled"
if [[ -f "$logind_config" ]]; then
    mv -- "$logind_config" "$disabled_logind_config"
fi
systemctl daemon-reload

chmod 0755 \
    scripts/nvgs-session-control.sh \
    scripts/download-session-control.sh \
    scripts/gerry-session-control.sh \
    scripts/ensure-lan-ready.sh \
    scripts/ethernet-watchdog.sh \
    scripts/install-ethernet-watchdog.sh \
    scripts/network-repair-control.sh \
    scripts/refresh-download-mdns.sh \
    host/server_control_gui.py

"$project_dir/scripts/install-ethernet-watchdog.sh"

applications_dir="$desktop_home/.local/share/applications"
install -d -o "$desktop_user" -g "$desktop_group" -m 0755 \
    "$applications_dir"

desktop_dir="$desktop_home/Desktop"
if command -v runuser >/dev/null 2>&1 \
    && command -v xdg-user-dir >/dev/null 2>&1; then
    detected_desktop="$(
        runuser -u "$desktop_user" -- xdg-user-dir DESKTOP 2>/dev/null || true
    )"
    if [[ -n "$detected_desktop" ]]; then
        desktop_dir="$detected_desktop"
    fi
fi

if [[ "$project_dir" == *$'\n'* || "$project_dir" == *'"'* ]]; then
    echo "The project path contains unsupported characters: $project_dir" >&2
    exit 1
fi

launcher_file="$applications_dir/nvgs-server-control.desktop"
cat > "$launcher_file" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=NVGS Server Hub
Comment=Choose which local server to run
Exec=python3 "${project_dir}/host/server_control_gui.py"
Path=${project_dir}
Icon=network-server
Terminal=false
Categories=Development;System;
StartupNotify=true
StartupWMClass=nvgs-server-hub
EOF
chmod 0755 "$launcher_file"
chown "$desktop_user:$desktop_group" "$launcher_file"
if command -v update-desktop-database >/dev/null 2>&1; then
    runuser -u "$desktop_user" -- \
        update-desktop-database "$applications_dir" >/dev/null 2>&1 || true
fi

# Older versions copied a shortcut to the desktop. Ubuntu 22.04 may open that
# copy as text, while the Applications entry works correctly.
legacy_desktop_launcher="$desktop_dir/NVGS Server Control.desktop"
rm -f -- "$legacy_desktop_launcher"

if [[ "$refresh_only" == "true" ]]; then
    mapfile -t container_ids < <(docker compose ps -aq)
    if [[ "${#container_ids[@]}" -gt 0 ]]; then
        docker update --restart=no "${container_ids[@]}" >/dev/null
    fi

    running_services="$(docker compose ps --status running --services)"
    if grep -qx "app" <<< "$running_services"; then
        systemctl restart nvgs-monitor.service nvgs-auth-monitor.service
    else
        systemctl stop nvgs-monitor.service nvgs-auth-monitor.service \
            >/dev/null 2>&1 || true
    fi

    echo "NVGS desktop-controlled mode was refreshed."
    exit 0
fi

# Existing containers remember their previous restart rule. Recreate them once
# with the new "no restart" rule, then stop them cleanly.
docker compose up -d --force-recreate
docker compose stop

echo
echo "NVGS Server Hub is installed."
echo "Automatic Ethernet recovery is enabled."
echo "View it with: sudo journalctl -u nvgs-ethernet-watchdog.service -f"
echo "Reboot once so Ubuntu returns to its normal lid and sleep behavior."
echo
echo "After reboot:"
echo "  1. Open 'NVGS Server Hub' from Ubuntu Applications."
echo "  2. Choose NVGS Server, Download Server, or Gery Chatbot Server."
echo "  3. Enter your Ubuntu password when asked."
echo "  4. Keep the selected server's control terminal open while it is needed."
echo "  5. Press Enter or close that terminal to stop the selected server."
echo
echo "Test the visible alert while NVGS is open:"
echo "  sudo ./scripts/test-alert.sh"
