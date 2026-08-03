#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

if [[ "${EUID}" -ne 0 ]]; then
    user_id="$(id -u)"
    runtime_dir="${XDG_RUNTIME_DIR:-/run/user/${user_id}}"
    overlay_socket="$runtime_dir/nvgs-alert-overlay.sock"
    controller_lock="$runtime_dir/nvgs-server-control.lock"

    exec 8> "$controller_lock"
    if ! flock -n 8; then
        echo "NVGS Server Control is already open." >&2
        read -r -p "Press Enter to close..." _
        exit 1
    fi

    if ! "$project_dir/scripts/ensure-lan-ready.sh"; then
        echo "NVGS stopped before startup because the LAN could not be recovered." >&2
        read -r -p "Press Enter to close..." _
        exit 1
    fi

    if ! "$project_dir/scripts/refresh-dynamic-lan.sh"; then
        echo "NVGS stopped before startup because its LAN address could not refresh." >&2
        read -r -p "Press Enter to close..." _
        exit 1
    fi

    overlay_pid=""
    stop_overlay() {
        trap - EXIT HUP INT TERM
        if [[ -n "$overlay_pid" ]] && kill -0 "$overlay_pid" 2>/dev/null; then
            kill "$overlay_pid" 2>/dev/null || true
            wait "$overlay_pid" 2>/dev/null || true
        fi
        rm -f -- "$overlay_socket"
    }
    trap stop_overlay EXIT HUP INT TERM

    rm -f -- "$overlay_socket"
    python3 host/nvgs_alert_overlay.py --socket "$overlay_socket" &
    overlay_pid="$!"

    for _attempt in {1..50}; do
        if [[ -S "$overlay_socket" ]]; then
            break
        fi
        if ! kill -0 "$overlay_pid" 2>/dev/null; then
            break
        fi
        sleep 0.1
    done

    if [[ ! -S "$overlay_socket" ]]; then
        echo "WARNING: Full-screen alerts could not start." >&2
        echo "Small desktop notifications and journal alerts remain active." >&2
    fi

    set +e
    sudo -- "$0"
    controller_status="$?"
    set -e
    stop_overlay
    exit "$controller_status"
fi

if [[ ! -f .env ]]; then
    echo "NVGS cannot start because .env is missing." >&2
    echo "Run ./scripts/bootstrap-secrets.sh first." >&2
    read -r -p "Press Enter to close..." _
    exit 1
fi

host_mode="$(
    sed -n 's/^[[:space:]]*NVGS_HOST_MODE[[:space:]]*=[[:space:]]*//p' .env \
        | tail -n 1 \
        | tr -d '\r'
)"
if [[ "${host_mode:-always_on}" != "on_demand" ]]; then
    echo "NVGS is configured for always-on mode." >&2
    echo "Run this once to enable the desktop controller:" >&2
    echo "  sudo ./scripts/install-app-controlled-mode.sh" >&2
    read -r -p "Press Enter to close..." _
    exit 1
fi

"$project_dir/scripts/refresh-mdns-alias.sh"

read_env_value() {
    local key="$1"
    sed -n "s/^[[:space:]]*${key}[[:space:]]*=[[:space:]]*//p" .env \
        | tail -n 1 \
        | tr -d '\r'
}

server_address="$(read_env_value "SERVER_ADDRESS")"
network_interface="$(read_env_value "NVGS_ACTIVE_LAN_INTERFACE")"
network_interface="${network_interface:-$(read_env_value "NVGS_LAN_INTERFACE")}"
if [[ -z "$network_interface" ]]; then
    network_interface="$(
        ip route show default 2>/dev/null \
            | awk '/default/ {for (i=1; i<=NF; i++) if ($i=="dev") {print $(i+1); exit}}'
    )"
fi
if [[ ! "${server_address:-localhost}" =~ ^[A-Za-z0-9._:-]+$ ]]; then
    echo "SERVER_ADDRESS contains unsupported characters: $server_address" >&2
    exit 1
fi
if [[ ! "${network_interface:-auto}" =~ ^[A-Za-z0-9_.:-]+$ ]]; then
    echo "NVGS_LAN_INTERFACE contains unsupported characters: $network_interface" >&2
    exit 1
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

if [[ -f /etc/nvgs-monitor.env ]]; then
    set_monitor_env_value \
        "NVGS_APP_HEALTH_URL" \
        "https://${server_address:-localhost}/api/health/"
    set_monitor_env_value \
        "NVGS_NETWORK_INTERFACE" \
        "${network_interface:-auto}"
    chmod 0600 /etc/nvgs-monitor.env
fi

session_started=false

stop_session() {
    trap - EXIT HUP INT TERM

    if [[ "$session_started" == "true" ]]; then
        echo
        echo "Stopping NVGS alerts, website, and database..."
        systemctl stop nvgs-monitor.service nvgs-auth-monitor.service \
            >/dev/null 2>&1 || true
        docker compose stop db app notifications caddy || true
        echo "NVGS is stopped. Ticket data remains safely stored."
    fi
}
trap stop_session EXIT HUP INT TERM

echo "Starting NVGS website, database, and alerts..."
session_started=true
docker compose up -d
systemctl start nvgs-monitor.service nvgs-auth-monitor.service

running_services="$(docker compose ps --status running --services)"
for required_service in db app notifications caddy; do
    if ! grep -qx "$required_service" <<< "$running_services"; then
        echo "NVGS did not start correctly. Current container status:" >&2
        docker compose ps -a >&2 || true
        exit 1
    fi
done

client_setup_ready=false
stable_server_name="$(read_env_value "NVGS_LAN_SERVER_NAME")"
controller_user="${SUDO_USER:-}"
if [[ -n "$stable_server_name" && -n "$controller_user" ]]; then
    if sudo -u "$controller_user" -- \
        "$project_dir/scripts/build-client-setup.sh" >/dev/null; then
        client_setup_ready=true
    else
        echo "WARNING: The client setup ZIP could not be refreshed." >&2
        echo "The website remains available; rebuild the ZIP from Ubuntu later." >&2
    fi
fi

echo
docker compose ps
echo
echo "NVGS IS RUNNING"
echo "- Ticketing: https://${server_address:-localhost}/tickets/"
echo "- Health: https://${server_address:-localhost}/api/health/"
if [[ "$client_setup_ready" == "true" ]]; then
    echo "- Current Windows/Ubuntu setup ZIP: client-setup-output/NVGS-Client-Setup.zip"
fi
echo "- Full-screen warnings and alert monitoring are active."
echo "- Sleep and lid-close suspension are blocked while this window is open."
echo "- Keep the charger and Ethernet cable connected."
echo
echo "Press Enter to stop NVGS cleanly."
echo "Closing this window also stops it."
echo

systemd-inhibit \
    --what=sleep:idle:handle-lid-switch \
    --who="NVGS Server Control" \
    --why="NVGS server session is running" \
    --mode=block \
    bash -c 'read -r _'
