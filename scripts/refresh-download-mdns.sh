#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
    echo "This helper is run automatically by DownloadServer Control." >&2
    exit 1
fi

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

exec 9> /run/lock/nvgs-mdns-alias.lock
flock 9

read_env_value() {
    local key="$1"
    if [[ ! -f .env ]]; then
        return 0
    fi
    sed -n "s/^[[:space:]]*${key}[[:space:]]*=[[:space:]]*//p" .env \
        | tail -n 1 \
        | tr -d '\r'
}

mode="${1:-}"
requested_ip="${2:-}"
if [[ "$mode" != "--publish" && "$mode" != "--remove" ]]; then
    echo "Usage: $0 --publish IPV4_ADDRESS | --remove" >&2
    exit 1
fi

server_name="$(read_env_value "DOWNLOAD_SERVER_NAME")"
server_name="${server_name:-download-system.local}"
server_name="${server_name,,}"
state_file="/etc/nvgs-download-mdns-alias"
avahi_hosts="/etc/avahi/hosts"
system_hosts="/etc/hosts"
hosts_begin_marker="# BEGIN NVGS DOWNLOAD HOSTNAME"
hosts_end_marker="# END NVGS DOWNLOAD HOSTNAME"
previous_name=""
if [[ -f "$state_file" ]]; then
    previous_name="$(tr -d '\r\n' < "$state_file")"
fi

current_name=""
current_ip=""
if [[ "$mode" == "--publish" ]]; then
    current_name="$server_name"
    current_ip="$requested_ip"
fi

if [[ -n "$current_name" ]] \
    && [[ ! "$current_name" =~ ^[a-z0-9]([a-z0-9.-]*[a-z0-9])?\.local$ ]]; then
    echo "Unsupported DownloadServer mDNS hostname: $current_name" >&2
    exit 1
fi
if [[ -n "$current_ip" ]] \
    && [[ ! "$current_ip" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
    echo "Invalid DownloadServer IPv4 address for mDNS: $current_ip" >&2
    exit 1
fi
if [[ -n "$current_ip" ]]; then
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
    raise SystemExit(f"Refusing unusable DownloadServer IPv4 address: {address}")
PY
fi
if [[ -n "$current_name" ]] && ! command -v avahi-daemon >/dev/null 2>&1; then
    echo "Avahi is required for the $current_name local hostname." >&2
    echo "Install it once with:" >&2
    echo "  sudo apt install avahi-daemon libnss-mdns" >&2
    exit 1
fi

install -d -m 0755 /etc/avahi
temporary_file="$(mktemp)"
hosts_temporary_file="$(mktemp)"
cleanup() {
    rm -f -- "$temporary_file" "$hosts_temporary_file"
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
    printf '%s %s\n' "$current_ip" "$current_name" >> "$temporary_file"
fi
install -m 0644 "$temporary_file" "$avahi_hosts"

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
        "$current_ip" \
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
    echo "Published DownloadServer hostname: $current_name -> $current_ip"
else
    rm -f -- "$state_file"
    if systemctl is-active --quiet avahi-daemon.service; then
        systemctl reload-or-restart avahi-daemon.service
    fi
fi

trap - EXIT
rm -f -- "$temporary_file" "$hosts_temporary_file"
