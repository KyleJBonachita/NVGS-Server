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

configured_interface="$(read_env_value "NVGS_LAN_INTERFACE")"
active_interface="$(read_env_value "NVGS_ACTIVE_LAN_INTERFACE")"
network_interface="${requested_interface:-$configured_interface}"

valid_interface() {
    local candidate="$1"
    [[ -n "$candidate" ]] \
        && [[ "$candidate" =~ ^[A-Za-z0-9_.:-]+$ ]] \
        && [[ -d "/sys/class/net/$candidate" ]]
}

interface_address() {
    local candidate="$1"
    ip -4 -o address show dev "$candidate" scope global 2>/dev/null \
        | awk 'NR == 1 {print $4}'
}

first_active_ethernet() {
    local candidate
    local candidate_type
    while read -r candidate; do
        candidate_type=""
        if command -v nmcli >/dev/null 2>&1; then
            candidate_type="$(
                nmcli -g GENERAL.TYPE device show "$candidate" 2>/dev/null \
                    | head -n 1 \
                    || true
            )"
        fi
        if [[ "$candidate_type" == "ethernet" ]] \
            || { [[ -z "$candidate_type" ]] \
                && [[ "$candidate" == en* || "$candidate" == eth* ]]; }; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done < <(
        ip -4 -o address show scope global 2>/dev/null \
            | awk '$2 !~ /^(lo|docker|br-|veth|virbr|podman|tailscale)/ {
                if (!seen[$2]++) print $2
            }'
    )
    return 1
}

if [[ -n "$requested_interface" ]] && ! valid_interface "$requested_interface"; then
    echo "Unknown or unsupported network interface: $requested_interface" >&2
    exit 1
fi

address_cidr=""
if [[ -n "$requested_interface" ]]; then
    network_interface="$requested_interface"
    address_cidr="$(interface_address "$network_interface")"
elif valid_interface "$configured_interface"; then
    # An interface explicitly selected in an earlier invocation stays selected
    # while it has an address. This preserves the documented Wi-Fi workaround
    # for sites whose access points isolate wireless clients from wired LAN.
    network_interface="$configured_interface"
    address_cidr="$(interface_address "$network_interface")"
fi

if [[ -z "$requested_interface" && -z "$address_cidr" ]]; then
    # Prefer a usable wired adapter even when Wi-Fi remains Ubuntu's current
    # default route only when no selected interface is currently usable.
    detected_interface="$(first_active_ethernet || true)"
    if valid_interface "$detected_interface"; then
        network_interface="$detected_interface"
        address_cidr="$(interface_address "$network_interface")"
    fi
fi

# Wi-Fi remains an allowed fallback when no Ethernet adapter has an address.
if [[ -z "$requested_interface" && -z "$address_cidr" ]]; then
    detected_interface="$(
        ip -4 route show default 2>/dev/null \
            | awk '/default/ {for (i=1; i<=NF; i++) if ($i=="dev") {print $(i+1); exit}}'
    )"
    if valid_interface "$detected_interface"; then
        network_interface="$detected_interface"
        address_cidr="$(interface_address "$network_interface")"
    fi
fi

if [[ -z "$requested_interface" && -z "$address_cidr" ]]; then
    detected_interface="$(
        ip -4 -o address show scope global 2>/dev/null \
            | awk '$2 !~ /^(lo|docker|br-|veth|virbr|podman|tailscale)/ {
                print $2; exit
            }'
    )"
    if valid_interface "$detected_interface"; then
        network_interface="$detected_interface"
        address_cidr="$(interface_address "$network_interface")"
    fi
fi

current_ip="${address_cidr%%/*}"
if [[ -z "$current_ip" ]]; then
    echo "No usable IPv4 LAN address was detected." >&2
    echo "Connect Ethernet or Wi-Fi and choose NVGS Server in the Hub again." >&2
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
if [[ -n "$requested_interface" ]]; then
    configured_interface="$requested_interface"
elif [[ -z "$configured_interface" ]]; then
    configured_interface="$network_interface"
fi
set_env_value "NVGS_LAN_INTERFACE" "$configured_interface"
set_env_value "NVGS_ACTIVE_LAN_INTERFACE" "$network_interface"
set_env_value "NVGS_LAN_SERVER_NAME" "$server_name"
set_env_value "SERVER_BIND_IP" "$current_ip"
set_env_value "SERVER_ADDRESS" "$server_address"
set_env_value "CADDY_SITE_ADDRESSES" "\"$caddy_site_addresses\""
set_env_value "DJANGO_ALLOWED_HOSTS" "$allowed_hosts"
set_env_value "DJANGO_CSRF_TRUSTED_ORIGINS" "$trusted_origins"
set_env_value "APPSCRIPT_SSO_SUCCESS_REDIRECT" "/tickets/"
set_env_value "TICKET_NOTIFICATION_PUBLIC_BASE_URL" "https://$server_address"
chmod 600 .env

if [[ "$old_ip" == "$current_ip" ]]; then
    echo "Dynamic LAN address confirmed: $current_ip ($network_interface)"
else
    echo "Dynamic LAN address refreshed: ${old_ip:-not set} -> $current_ip"
fi
if [[ -n "$active_interface" && "$active_interface" != "$network_interface" ]]; then
    echo "Active LAN adapter changed: $active_interface -> $network_interface"
fi
if [[ "$configured_interface" != "$network_interface" ]]; then
    echo "Preferred adapter $configured_interface is unavailable; using $network_interface temporarily."
fi
echo "NVGS link: https://$server_address/tickets/"

if [[ "$old_server_address" != "$server_address" ]] \
    && [[ "$(read_env_value "APPSCRIPT_SSO_ENABLED")" == "true" ]]; then
    echo "NOTICE: Update the Apps Script callback for the new server link:"
    echo "  ./scripts/appscript-login-setup.sh prepare"
fi
