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

read_env_value() {
    local key="$1"
    sed -n "s/^[[:space:]]*${key}[[:space:]]*=[[:space:]]*//p" .env \
        | tail -n 1 \
        | tr -d '\r'
}

default_interface="$(
    ip route show default 2>/dev/null \
        | awk '/default/ {for (i=1; i<=NF; i++) if ($i=="dev") {print $(i+1); exit}}'
)"
default_gateway="$(
    ip route show default 2>/dev/null \
        | awk '/default/ {for (i=1; i<=NF; i++) if ($i=="via") {print $(i+1); exit}}'
)"
current_addresses="$(
    ip -4 -o address show scope global 2>/dev/null \
        | awk '{print $2 " " $4}'
)"
server_bind_ip="$(read_env_value "SERVER_BIND_IP")"
server_address="$(read_env_value "SERVER_ADDRESS")"
lan_mode="$(read_env_value "NVGS_LAN_MODE")"
lan_interface="$(read_env_value "NVGS_LAN_INTERFACE")"
active_lan_interface="$(read_env_value "NVGS_ACTIVE_LAN_INTERFACE")"
lan_server_name="$(read_env_value "NVGS_LAN_SERVER_NAME")"

echo "NVGS LAN readiness (read-only)"
echo
echo "Default interface: ${default_interface:-not detected}"
echo "Default gateway: ${default_gateway:-not detected}"
echo "Current Ubuntu IPv4 addresses:"
if [[ -n "$current_addresses" ]]; then
    while IFS= read -r address; do
        echo "  $address"
    done <<< "$current_addresses"
else
    echo "  none detected"
fi
echo
echo "NVGS currently configured for:"
echo "  NVGS_LAN_MODE=${lan_mode:-manual}"
echo "  NVGS_LAN_INTERFACE=${lan_interface:-not set}"
echo "  NVGS_ACTIVE_LAN_INTERFACE=${active_lan_interface:-not set}"
echo "  NVGS_LAN_SERVER_NAME=${lan_server_name:-not set}"
echo "  SERVER_BIND_IP=${server_bind_ip:-not set}"
echo "  SERVER_ADDRESS=${server_address:-not set}"
echo

if [[ "${server_bind_ip:-127.0.0.1}" == "127.0.0.1" ]]; then
    echo "Result: LOCAL-ONLY"
    echo "The server is not exposed to the production LAN."
elif ip -4 -o address show | grep -Fqw -- "$server_bind_ip"; then
    echo "Result: ADDRESS PRESENT"
    echo "Ubuntu currently owns the configured bind address."
else
    echo "Result: CONFIGURED ADDRESS IS NOT PRESENT"
    echo "Caddy cannot bind until Ubuntu owns that address."
fi

echo
echo "Running Docker services:"
docker compose ps --status running --services 2>/dev/null || true
echo
echo "Important: a current DHCP address is not automatically approved or reserved."
echo "Ask the network owner for the reservation/address before running:"
echo "  ./scripts/configure-approved-lan.sh ASSIGNED_IPV4"
