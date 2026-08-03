#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
    echo "This helper runs automatically when NVGS is chosen in Server Hub." >&2
    exit 1
fi

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

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

lan_mode="$(read_env_value "NVGS_LAN_MODE")"
server_name="$(read_env_value "NVGS_LAN_SERVER_NAME")"
server_ip="$(read_env_value "SERVER_BIND_IP")"
state_file="/etc/nvgs-mdns-alias"
avahi_hosts="/etc/avahi/hosts"
system_hosts="/etc/hosts"
hosts_begin_marker="# BEGIN NVGS LOCAL HOSTNAME"
hosts_end_marker="# END NVGS LOCAL HOSTNAME"
previous_name=""
if [[ -f "$state_file" ]]; then
    previous_name="$(tr -d '\r\n' < "$state_file")"
fi

current_name=""
if [[ "$lan_mode" == "dynamic" && "$server_name" == *.local ]]; then
    current_name="$server_name"
fi
if [[ -z "$current_name" && -z "$previous_name" ]]; then
    exit 0
fi

if [[ ! "$current_name" =~ ^[a-z0-9]([a-z0-9.-]*[a-z0-9])?\.local$ ]]; then
    if [[ -n "$current_name" ]]; then
        echo "Unsupported NVGS mDNS hostname: $current_name" >&2
        exit 1
    fi
fi
if [[ -n "$current_name" ]] \
    && [[ ! "$server_ip" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
    echo "Invalid SERVER_BIND_IP for mDNS: $server_ip" >&2
    exit 1
fi
if [[ -n "$current_name" ]] && ! command -v avahi-daemon >/dev/null 2>&1; then
    echo "Avahi is required for the $current_name local hostname." >&2
    echo "Install the approved Ubuntu package, then reopen the controller:" >&2
    echo "  sudo apt install avahi-daemon libnss-mdns" >&2
    exit 1
fi

install -d -m 0755 /etc/avahi
temporary_file="$(mktemp)"
hosts_temporary_file="$(mktemp)"
cleanup() {
    rm -f -- "$temporary_file"
    rm -f -- "$hosts_temporary_file"
}
trap cleanup EXIT

if [[ -f "$avahi_hosts" ]]; then
    awk \
        -v previous_name="$previous_name" \
        -v current_name="$current_name" \
        'NF >= 2 && ($2 == previous_name || $2 == current_name) {next} {print}' \
        "$avahi_hosts" > "$temporary_file"
fi
if [[ -n "$current_name" ]]; then
    printf '%s %s\n' "$server_ip" "$current_name" >> "$temporary_file"
fi

install -m 0644 "$temporary_file" "$avahi_hosts"

# Avahi publishes the alias to other machines. A matching /etc/hosts entry
# also guarantees that the Ubuntu server can resolve its own friendly name.
if [[ -f "$system_hosts" ]]; then
    awk \
        -v begin_marker="$hosts_begin_marker" \
        -v end_marker="$hosts_end_marker" \
        '$0 == begin_marker {managed=1; next}
         $0 == end_marker {managed=0; next}
         !managed {print}' \
        "$system_hosts" > "$hosts_temporary_file"
fi
if [[ -n "$current_name" ]]; then
    if [[ -s "$hosts_temporary_file" ]] \
        && [[ -n "$(tail -c 1 "$hosts_temporary_file")" ]]; then
        printf '\n' >> "$hosts_temporary_file"
    fi
    printf '%s\n%s %s\n%s\n' \
        "$hosts_begin_marker" \
        "$server_ip" \
        "$current_name" \
        "$hosts_end_marker" \
        >> "$hosts_temporary_file"
fi
install -m 0644 "$hosts_temporary_file" "$system_hosts"

if [[ -n "$current_name" ]]; then
    printf '%s\n' "$current_name" > "$state_file"
    chmod 0644 "$state_file"
    systemctl enable --now avahi-daemon.service >/dev/null
    systemctl reload-or-restart avahi-daemon.service
    echo "Published NVGS local hostname: $current_name -> $server_ip"
else
    rm -f -- "$state_file"
    if systemctl is-active --quiet avahi-daemon.service; then
        systemctl reload-or-restart avahi-daemon.service
    fi
fi

trap - EXIT
rm -f -- "$temporary_file" "$hosts_temporary_file"
