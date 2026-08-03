#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

require_ethernet=false
if [[ "${1:-}" == "--require-ethernet" ]]; then
    require_ethernet=true
elif [[ -n "${1:-}" ]]; then
    echo "Usage: $0 [--require-ethernet]" >&2
    exit 1
fi

if [[ "${EUID}" -eq 0 ]]; then
    echo "Run network recovery from the normal Ubuntu desktop account." >&2
    exit 1
fi

read_env_value() {
    local key="$1"
    if [[ ! -f .env ]]; then
        return 0
    fi
    sed -n "s/^[[:space:]]*${key}[[:space:]]*=[[:space:]]*//p" .env \
        | tail -n 1 \
        | tr -d '\r'
}

has_ipv4() {
    local interface_name="$1"
    ip -4 -o address show dev "$interface_name" scope global 2>/dev/null \
        | grep -q .
}

is_physical_lan_type() {
    [[ "$1" == "ethernet" || "$1" == "wifi" ]]
}

is_physical_interface() {
    local interface_name="$1"
    [[ -n "$interface_name" && -d "/sys/class/net/$interface_name" ]] \
        || return 1
    case "$interface_name" in
        lo|docker*|br-*|veth*|virbr*|podman*|tailscale*) return 1 ;;
    esac
    [[ -e "/sys/class/net/$interface_name/device" ]]
}

interface_type() {
    local interface_name="$1"
    local detected_type=""
    if ! is_physical_interface "$interface_name"; then
        printf 'other\n'
        return 0
    fi
    if command -v nmcli >/dev/null 2>&1; then
        detected_type="$(
            nmcli -g GENERAL.TYPE device show "$interface_name" 2>/dev/null \
                | head -n 1 \
                || true
        )"
    fi
    if is_physical_lan_type "$detected_type"; then
        printf '%s\n' "$detected_type"
    elif [[ -d "/sys/class/net/$interface_name/wireless" ]] \
        || [[ "$interface_name" == wl* ]]; then
        printf 'wifi\n'
    elif [[ "$interface_name" == en* || "$interface_name" == eth* ]]; then
        printf 'ethernet\n'
    else
        printf 'other\n'
    fi
}

interface_address() {
    local interface_name="$1"
    ip -4 -o address show dev "$interface_name" scope global 2>/dev/null \
        | awk 'NR == 1 {split($4, value, "/"); print value[1]}'
}

append_candidate() {
    local interface_name="$1"
    local existing
    [[ -n "$interface_name" ]] || return 0
    for existing in "${candidates[@]}"; do
        [[ "$existing" == "$interface_name" ]] && return 0
    done
    candidates+=("$interface_name")
}

print_driver_diagnostics() {
    echo
    echo "Network device diagnostics:"
    ip -brief link 2>/dev/null || true
    ip -4 route 2>/dev/null || true
    if command -v nmcli >/dev/null 2>&1; then
        nmcli -f DEVICE,TYPE,STATE,CONNECTION device status 2>/dev/null || true
    fi
    if command -v lspci >/dev/null 2>&1; then
        lspci -nnk 2>/dev/null \
            | grep -A3 -Ei 'ethernet controller|network controller' \
            || true
    fi
    echo
    echo "If the Ethernet device is absent above, this is probably a driver,"
    echo "kernel, firmware, dock/adapter, or hardware issue. Server Hub will not"
    echo "guess and reload an unknown kernel driver automatically."
    echo "Useful follow-up command:"
    echo "  sudo journalctl -k -b --no-pager | grep -Ei 'ethernet|network|link|firmware|r816|e1000|igc|tg3'"
}

configured_interface="$(read_env_value "NVGS_LAN_INTERFACE")"
default_interface="$(
    ip -4 route show default 2>/dev/null \
        | awk '/default/ {for (i=1; i<=NF; i++) if ($i=="dev") {print $(i+1); exit}}'
)"

candidates=()
append_candidate "$configured_interface"
append_candidate "$default_interface"

if command -v nmcli >/dev/null 2>&1; then
    while IFS=: read -r device device_type _state; do
        if is_physical_lan_type "$device_type" \
            && is_physical_interface "$device"; then
            append_candidate "$device"
        fi
    done < <(nmcli -t -f DEVICE,TYPE,STATE device status 2>/dev/null || true)
else
    while read -r device; do
        append_candidate "$device"
    done < <(
        ip -4 -o link show 2>/dev/null \
            | awk -F': ' '$2 !~ /^(lo|docker|br-|veth|virbr|podman|tailscale)/ {print $2}' \
            | cut -d@ -f1
    )
fi

ethernet_candidates=()
wifi_candidates=()
for candidate in "${candidates[@]}"; do
    case "$(interface_type "$candidate")" in
        ethernet) ethernet_candidates+=("$candidate") ;;
        wifi) wifi_candidates+=("$candidate") ;;
    esac
done

for candidate in "${ethernet_candidates[@]}"; do
    if [[ -d "/sys/class/net/$candidate" ]] && has_ipv4 "$candidate"; then
        echo "Ethernet ready: $candidate has $(interface_address "$candidate")"
        exit 0
    fi
done

device_seen=false
carrier_seen=false
network_manager_ready=false
if command -v nmcli >/dev/null 2>&1 \
    && systemctl is-active --quiet NetworkManager.service; then
    network_manager_ready=true
    nmcli networking on >/dev/null 2>&1 || true
fi

reconnect_candidate() {
    local candidate="$1"
    local device_type="$2"
    local state
    local managed
    local carrier

    if [[ ! -d "/sys/class/net/$candidate" ]]; then
        echo "- $candidate is configured but missing from the kernel device list."
        return 1
    fi
    device_seen=true

    state="$(
        nmcli -g GENERAL.STATE device show "$candidate" 2>/dev/null \
            | head -n 1 \
            || true
    )"
    managed="$(
        nmcli -g GENERAL.NM-MANAGED device show "$candidate" 2>/dev/null \
            | head -n 1 \
            || true
    )"
    carrier="$(cat "/sys/class/net/$candidate/carrier" 2>/dev/null || true)"

    if [[ "$device_type" == "ethernet" && "$carrier" != "1" ]]; then
        echo "- $candidate has no Ethernet carrier; check the cable, modem, or dock."
        return 1
    fi
    carrier_seen=true
    if [[ "$managed" == "no" || "$state" == *"unmanaged"* ]]; then
        echo "- $candidate is not managed by NetworkManager; leaving its configuration unchanged."
        return 1
    fi

    echo "- Reconnecting $candidate using its best saved connection profile..."
    nmcli --wait 20 connection up ifname "$candidate" >/dev/null 2>&1 || true

    for _attempt in {1..12}; do
        if has_ipv4 "$candidate"; then
            echo "${device_type^} recovered: $candidate has $(interface_address "$candidate")"
            return 0
        fi
        sleep 1
    done
    echo "- $candidate did not receive an IPv4 address."
    return 1
}

if [[ "$network_manager_ready" == "true" ]]; then
    if [[ "${#ethernet_candidates[@]}" -gt 0 ]]; then
        echo "Trying Ethernet before using Wi-Fi..."
    fi
    for candidate in "${ethernet_candidates[@]}"; do
        if reconnect_candidate "$candidate" "ethernet"; then
            exit 0
        fi
    done
fi

if [[ "$require_ethernet" == "true" ]]; then
    echo "Ethernet could not be restored; Wi-Fi was left connected as a fallback." >&2
    print_driver_diagnostics
    exit 4
fi

for candidate in "${wifi_candidates[@]}"; do
    if [[ -d "/sys/class/net/$candidate" ]] && has_ipv4 "$candidate"; then
        echo "Wi-Fi fallback: $candidate has $(interface_address "$candidate")"
        exit 0
    fi
done

if [[ "$network_manager_ready" == "true" ]]; then
    nmcli radio wifi on >/dev/null 2>&1 || true
    for candidate in "${wifi_candidates[@]}"; do
        if reconnect_candidate "$candidate" "wifi"; then
            exit 0
        fi
    done
else
    echo "No LAN address is active and NetworkManager recovery is unavailable." >&2
fi

if [[ "$device_seen" == "false" ]]; then
    echo "No physical Ethernet or Wi-Fi device is visible to Ubuntu." >&2
elif [[ "$carrier_seen" == "false" ]]; then
    echo "Ubuntu sees the adapters, but no usable physical link is present." >&2
else
    echo "The adapters are present, but no saved connection produced an IPv4 address." >&2
fi
print_driver_diagnostics
exit 3
