#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

if [[ "${EUID}" -ne 0 ]]; then
    exec sudo -- "$0"
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
for required_service in db app caddy; do
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
echo "- Alerts are active."
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
