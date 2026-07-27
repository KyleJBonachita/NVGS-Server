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

session_started=false

stop_session() {
    trap - EXIT HUP INT TERM

    if [[ "$session_started" == "true" ]]; then
        echo
        echo "Stopping NVGS alerts, website, and database..."
        systemctl stop nvgs-monitor.service nvgs-auth-monitor.service \
            >/dev/null 2>&1 || true
        docker compose stop || true
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

echo
docker compose ps
echo
echo "NVGS IS RUNNING"
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
