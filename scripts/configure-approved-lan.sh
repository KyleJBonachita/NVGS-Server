#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

usage() {
    cat <<'EOF'
Use only after the LAN administrator has assigned or reserved an IPv4 address.

Usage:
  ./scripts/configure-approved-lan.sh ASSIGNED_IPV4 [APPROVED_DNS_NAME]

Examples:
  ./scripts/configure-approved-lan.sh 10.20.30.40
  ./scripts/configure-approved-lan.sh 10.20.30.40 nvgs-server.internal

This configures NVGS to use an address already present on Ubuntu. It does not
choose an address or change Ubuntu's NetworkManager settings.
EOF
}

if [[ "${EUID}" -eq 0 ]]; then
    echo "Run this from your normal Ubuntu account, without sudo." >&2
    exit 1
fi
if [[ ! -f .env ]]; then
    echo "Missing .env. Run ./scripts/bootstrap-secrets.sh first." >&2
    exit 1
fi
if [[ "$#" -lt 1 || "$#" -gt 2 ]]; then
    usage >&2
    exit 1
fi

assigned_ip="$1"
server_address="${2:-$assigned_ip}"

python3 - "$assigned_ip" <<'PY'
import ipaddress
import sys

try:
    address = ipaddress.ip_address(sys.argv[1])
except ValueError as exc:
    raise SystemExit(f"Invalid IP address: {exc}")
if address.version != 4:
    raise SystemExit("This helper currently expects an assigned IPv4 address.")
if address.is_loopback or address.is_multicast or address.is_unspecified:
    raise SystemExit("Use the assigned private LAN address, not a special address.")
PY

if [[ ! "$server_address" =~ ^[A-Za-z0-9.-]+$ ]]; then
    echo "The DNS name contains unsupported characters: $server_address" >&2
    exit 1
fi

if ! ip -4 -o address show | grep -Fqw -- "$assigned_ip"; then
    echo "Ubuntu does not currently have $assigned_ip on a network interface." >&2
    echo "Stop here. Ask for the DHCP reservation/static settings, apply them" >&2
    echo "in Ubuntu, reconnect Ethernet, then run this command again." >&2
    exit 1
fi

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

allowed_hosts="${server_address},${assigned_ip},localhost,127.0.0.1"
trusted_origins="https://${server_address}"
if [[ "$server_address" != "$assigned_ip" ]]; then
    trusted_origins="${trusted_origins},https://${assigned_ip}"
fi

set_env_value "SERVER_BIND_IP" "$assigned_ip"
set_env_value "SERVER_ADDRESS" "$server_address"
set_env_value "DJANGO_ALLOWED_HOSTS" "$allowed_hosts"
set_env_value "DJANGO_CSRF_TRUSTED_ORIGINS" "$trusted_origins"
set_env_value "APPSCRIPT_SSO_SUCCESS_REDIRECT" "/tickets/"
set_env_value "NVGS_LAN_MODE" "manual"
set_env_value "NVGS_LAN_INTERFACE" ""
set_env_value "NVGS_LAN_SERVER_NAME" ""
chmod 600 .env

host_mode="$(
    sed -n 's/^[[:space:]]*NVGS_HOST_MODE[[:space:]]*=[[:space:]]*//p' .env \
        | tail -n 1 \
        | tr -d '\r'
)"
running_services="$(docker compose ps --status running --services 2>/dev/null || true)"
if grep -qx "app" <<< "$running_services" || [[ "$host_mode" != "on_demand" ]]; then
    docker compose up -d --build
    ./scripts/export-client-ca.sh
    echo "NVGS is available at https://${server_address}/tickets/"
else
    echo "LAN configuration saved."
    echo "Open NVGS Server Control to start the server, then run:"
    echo "  ./scripts/export-client-ca.sh"
fi

echo
echo "Refresh the Ubuntu monitor address:"
echo "  sudo ./scripts/install-ubuntu-host.sh"
echo
echo "If Apps Script login was prepared for localhost, run:"
echo "  ./scripts/appscript-login-setup.sh prepare"
echo "Then update NVGS_BRIDGE_CALLBACK_URL in Apps Script Script Properties."
echo
echo "Do not begin the pilot until one approved client trusts nvgs-local-ca.crt"
echo "and opens https://${server_address}/api/health/ without a warning."
