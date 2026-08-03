#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
    echo "Run this installer with sudo." >&2
    exit 1
fi

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

if [[ ! -f scripts/ethernet-watchdog.sh ]] \
    || [[ ! -f host/systemd/nvgs-ethernet-watchdog.service ]]; then
    echo "Ethernet watchdog files are missing." >&2
    exit 1
fi

read_existing_value() {
    local key="$1"
    if [[ -f /etc/nvgs-ethernet-watchdog.env ]]; then
        sed -n "s/^[[:space:]]*${key}[[:space:]]*=[[:space:]]*//p" \
            /etc/nvgs-ethernet-watchdog.env \
            | tail -n 1 \
            | tr -d '\r'
    fi
}

is_ethernet_interface() {
    local candidate="$1"
    local candidate_type=""
    [[ -n "$candidate" && -d "/sys/class/net/$candidate" ]] || return 1
    if command -v nmcli >/dev/null 2>&1; then
        candidate_type="$(
            nmcli -g GENERAL.TYPE device show "$candidate" 2>/dev/null \
                | head -n 1 \
                || true
        )"
    fi
    [[ "$candidate_type" == "ethernet" ]] \
        || { [[ -z "$candidate_type" ]] \
            && [[ "$candidate" == en* || "$candidate" == eth* ]]; }
}

ethernet_interface="$(read_existing_value "NVGS_ETHERNET_INTERFACE")"
if ! is_ethernet_interface "$ethernet_interface"; then
    ethernet_interface=""
fi
if [[ -z "$ethernet_interface" ]] && command -v nmcli >/dev/null 2>&1; then
    ethernet_interface="$(
        nmcli -t -f DEVICE,TYPE device status 2>/dev/null \
            | awk -F: '$2 == "ethernet" {print $1; exit}'
    )"
fi
if [[ -z "$ethernet_interface" ]]; then
    for candidate_path in /sys/class/net/en* /sys/class/net/eth*; do
        if [[ -d "$candidate_path" ]]; then
            ethernet_interface="$(basename "$candidate_path")"
            break
        fi
    done
fi

check_seconds="$(read_existing_value "NVGS_ETHERNET_CHECK_SECONDS")"
reload_cooldown="$(read_existing_value "NVGS_ETHERNET_RELOAD_COOLDOWN_SECONDS")"
max_reloads="$(read_existing_value "NVGS_ETHERNET_MAX_DRIVER_RELOADS")"
disable_eee="$(read_existing_value "NVGS_ETHERNET_DISABLE_EEE")"
prevent_runtime_pm="$(read_existing_value "NVGS_ETHERNET_PREVENT_RUNTIME_PM")"

install -d -m 0755 /usr/local/libexec
install -m 0755 \
    scripts/ethernet-watchdog.sh \
    /usr/local/libexec/nvgs-ethernet-watchdog
install -m 0644 \
    host/systemd/nvgs-ethernet-watchdog.service \
    /etc/systemd/system/nvgs-ethernet-watchdog.service

cat > /etc/nvgs-ethernet-watchdog.env <<EOF
NVGS_ETHERNET_INTERFACE=${ethernet_interface}
NVGS_ETHERNET_CHECK_SECONDS=${check_seconds:-15}
NVGS_ETHERNET_RELOAD_COOLDOWN_SECONDS=${reload_cooldown:-600}
NVGS_ETHERNET_MAX_DRIVER_RELOADS=${max_reloads:-1}
NVGS_ETHERNET_DISABLE_EEE=${disable_eee:-true}
NVGS_ETHERNET_PREVENT_RUNTIME_PM=${prevent_runtime_pm:-true}
EOF
chmod 0600 /etc/nvgs-ethernet-watchdog.env

if ! command -v ethtool >/dev/null 2>&1; then
    echo "WARNING: ethtool is not installed; EEE control will be skipped." >&2
    echo "Install it with: sudo apt install ethtool" >&2
fi

systemctl daemon-reload
systemctl enable nvgs-ethernet-watchdog.service >/dev/null
systemctl restart nvgs-ethernet-watchdog.service

echo "Automatic Ethernet recovery installed for ${ethernet_interface:-auto-detection}."
