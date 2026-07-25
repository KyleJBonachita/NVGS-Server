#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
    echo "Run this setup with sudo:" >&2
    echo "  sudo ./scripts/install-ubuntu-host.sh" >&2
    exit 1
fi

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

if [[ ! -d /etc/systemd/system ]]; then
    echo "This script must be run on an Ubuntu system using systemd." >&2
    exit 1
fi

server_address="localhost"
if [[ -f .env ]]; then
    configured_address="$(
        sed -n 's/^[[:space:]]*SERVER_ADDRESS[[:space:]]*=[[:space:]]*//p' .env \
            | tail -n 1 \
            | tr -d '\r'
    )"
    if [[ -n "$configured_address" ]]; then
        server_address="$configured_address"
    fi
fi

if [[ ! "$server_address" =~ ^[A-Za-z0-9._:-]+$ ]]; then
    echo "SERVER_ADDRESS contains unsupported characters: $server_address" >&2
    exit 1
fi

escaped_project_dir="${project_dir//\\/\\\\}"
escaped_project_dir="${escaped_project_dir//&/\\&}"
escaped_project_dir="${escaped_project_dir//|/\\|}"

install -d -m 0755 /etc/systemd/logind.conf.d
install -m 0644 \
    host/systemd/50-nvgs-server.conf \
    /etc/systemd/logind.conf.d/50-nvgs-server.conf

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
    chmod 0600 /etc/nvgs-monitor.env
    echo "Created /etc/nvgs-monitor.env."
else
    sed -i \
        "s|^NVGS_APP_HEALTH_URL=.*|NVGS_APP_HEALTH_URL=https://${server_address}/api/health/|" \
        /etc/nvgs-monitor.env
    sed -i \
        "s|^NVGS_CA_FILE=.*|NVGS_CA_FILE=${escaped_project_dir}/nvgs-local-ca.crt|" \
        /etc/nvgs-monitor.env
    chmod 0600 /etc/nvgs-monitor.env
    echo "Kept existing alert choices and refreshed the application address."
fi

# This prevents desktop settings or accidental lid closure from suspending the
# server. It is reversible with the unmask command printed below.
systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target
systemctl daemon-reload
systemctl enable nvgs-monitor.service nvgs-auth-monitor.service
systemctl restart nvgs-monitor.service nvgs-auth-monitor.service

echo
echo "Ubuntu host setup installed."
echo "Anti-sleep takes full effect after the next reboot."
echo
echo "View condition alerts:"
echo "  journalctl -u nvgs-monitor.service -f"
echo
echo "View rejected-login alerts:"
echo "  journalctl -u nvgs-auth-monitor.service -f"
echo
echo "Configure an approved remote webhook:"
echo "  sudo nano /etc/nvgs-monitor.env"
echo "  sudo systemctl restart nvgs-monitor.service nvgs-auth-monitor.service"
echo
echo "Undo the sleep-target block if this laptop stops being a server:"
echo "  sudo systemctl unmask sleep.target suspend.target hibernate.target hybrid-sleep.target"
