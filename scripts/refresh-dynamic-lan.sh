#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

if [[ "${EUID}" -eq 0 ]]; then
    echo "Run this from your normal Ubuntu account, without sudo." >&2
    exit 1
fi
if [[ ! -f .env ]]; then
    echo "Missing .env. Run ./scripts/bootstrap-secrets.sh first." >&2
    exit 1
fi
if [[ "$#" -gt 2 ]]; then
    echo "Usage: ./scripts/refresh-dynamic-lan.sh [INTERFACE] [STABLE_HOSTNAME]" >&2
    exit 1
fi

read_env_value() {
    local key="$1"
    sed -n "s/^[[:space:]]*${key}[[:space:]]*=[[:space:]]*//p" .env \
        | tail -n 1 \
        | tr -d '\r'
}

set_env_value() {
    local key="$1"
    local value="$2"
    local escaped_value
    escaped_value="${value//\\/\\\\}"
    escaped_value="${escaped_value//&/\\&}"
    escaped_value="${escaped_value//|/\\|}"

    if grep -q "^[[:space:]]*${key}[[:space:]]*=" .env; then
        sed -i \
            "s|^[[:space:]]*${key}[[:space:]]*=.*|${key}=${escaped_value}|" \
            .env
    else
        printf '\n%s=%s\n' "$key" "$value" >> .env
    fi
}

requested_interface="${1:-}"
requested_server_name="${2:-}"
lan_mode="$(read_env_value "NVGS_LAN_MODE")"
if [[ -n "$requested_interface" ]]; then
    lan_mode="dynamic"
elif [[ "${lan_mode:-manual}" != "dynamic" ]]; then
    exit 0
fi

network_interface="${requested_interface:-$(read_env_value "NVGS_LAN_INTERFACE")}"
if [[ -z "$network_interface" ]]; then
    echo "Dynamic LAN mode needs NVGS_LAN_INTERFACE in .env." >&2
    echo "Enable it once with:" >&2
    echo "  ./scripts/refresh-dynamic-lan.sh enp109s0" >&2
    exit 1
fi
if [[ ! "$network_interface" =~ ^[A-Za-z0-9_.:-]+$ ]] \
    || [[ ! -d "/sys/class/net/$network_interface" ]]; then
    echo "Unknown or unsupported network interface: $network_interface" >&2
    exit 1
fi

address_cidr="$(
    ip -4 -o address show dev "$network_interface" scope global 2>/dev/null \
        | awk 'NR == 1 {print $4}'
)"
current_ip="${address_cidr%%/*}"
if [[ -z "$current_ip" ]]; then
    echo "No IPv4 address is active on $network_interface." >&2
    echo "Connect Ethernet and try opening NVGS Server Control again." >&2
    exit 1
fi

python3 - "$current_ip" <<'PY'
import ipaddress
import sys

address = ipaddress.ip_address(sys.argv[1])
if (
    address.version != 4
    or address.is_loopback
    or address.is_link_local
    or address.is_multicast
    or address.is_unspecified
):
    raise SystemExit(f"Refusing unusable dynamic IPv4 address: {address}")
PY

old_ip="$(read_env_value "SERVER_BIND_IP")"
old_server_address="$(read_env_value "SERVER_ADDRESS")"
server_name="${requested_server_name:-$(read_env_value "NVGS_LAN_SERVER_NAME")}"
server_name="${server_name,,}"
server_address="$current_ip"
caddy_site_addresses="$current_ip"
allowed_hosts="$current_ip,localhost,127.0.0.1"
trusted_origins="https://$current_ip"

if [[ -n "$server_name" ]]; then
    if [[ ! "$server_name" =~ ^[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?$ ]] \
        || [[ "$server_name" != *.* ]] \
        || [[ "$server_name" == *..* ]]; then
        echo "Unsupported stable hostname: $server_name" >&2
        exit 1
    fi

    if [[ "$server_name" != *.local ]]; then
        resolved_addresses="$(
            getent ahostsv4 "$server_name" 2>/dev/null \
                | awk '{print $1}' \
                | sort -u \
                || true
        )"
        if ! grep -Fxq "$current_ip" <<< "$resolved_addresses"; then
            echo "$server_name does not resolve to $current_ip on Ubuntu." >&2
            echo "Check internal DNS before enabling this stable name." >&2
            exit 1
        fi
    fi

    server_address="$server_name"
    caddy_site_addresses="$server_name https://$current_ip"
    allowed_hosts="$server_name,$current_ip,localhost,127.0.0.1"
    trusted_origins="https://$server_name,https://$current_ip"
fi

set_env_value "NVGS_LAN_MODE" "dynamic"
set_env_value "NVGS_LAN_INTERFACE" "$network_interface"
set_env_value "NVGS_LAN_SERVER_NAME" "$server_name"
set_env_value "SERVER_BIND_IP" "$current_ip"
set_env_value "SERVER_ADDRESS" "$server_address"
set_env_value "CADDY_SITE_ADDRESSES" "\"$caddy_site_addresses\""
set_env_value "DJANGO_ALLOWED_HOSTS" "$allowed_hosts"
set_env_value "DJANGO_CSRF_TRUSTED_ORIGINS" "$trusted_origins"
set_env_value "APPSCRIPT_SSO_SUCCESS_REDIRECT" "/tickets/"
chmod 600 .env

if [[ "$old_ip" == "$current_ip" ]]; then
    echo "Dynamic LAN address confirmed: $current_ip ($network_interface)"
else
    echo "Dynamic LAN address refreshed: ${old_ip:-not set} -> $current_ip"
fi
echo "NVGS link: https://$server_address/tickets/"

if [[ "$old_server_address" != "$server_address" ]] \
    && [[ "$(read_env_value "APPSCRIPT_SSO_ENABLED")" == "true" ]]; then
    echo "NOTICE: Update the Apps Script callback for the new server link:"
    echo "  ./scripts/appscript-login-setup.sh prepare"
fi
