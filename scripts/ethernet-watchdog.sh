#!/usr/bin/env bash
set -u

if [[ "${EUID}" -ne 0 ]]; then
    echo "Ethernet recovery requires root privileges." >&2
    exit 1
fi

mode="${1:---watch}"
force_driver_reload=false
if [[ "$mode" == "--once" && "${2:-}" == "--force-driver-reload" ]]; then
    force_driver_reload=true
elif [[ "$mode" != "--once" && "$mode" != "--watch" ]]; then
    echo "Usage: $0 --watch | --once [--force-driver-reload]" >&2
    exit 1
elif [[ -n "${2:-}" ]]; then
    echo "Usage: $0 --watch | --once [--force-driver-reload]" >&2
    exit 1
fi

check_seconds="${NVGS_ETHERNET_CHECK_SECONDS:-15}"
reload_cooldown="${NVGS_ETHERNET_RELOAD_COOLDOWN_SECONDS:-600}"
max_reloads="${NVGS_ETHERNET_MAX_DRIVER_RELOADS:-1}"
configured_interface="${NVGS_ETHERNET_INTERFACE:-}"
disable_eee="${NVGS_ETHERNET_DISABLE_EEE:-true}"
prevent_runtime_pm="${NVGS_ETHERNET_PREVENT_RUNTIME_PM:-true}"

for numeric_value in "$check_seconds" "$reload_cooldown" "$max_reloads"; do
    if [[ ! "$numeric_value" =~ ^[0-9]+$ ]]; then
        echo "Ethernet watchdog timing values must be non-negative integers." >&2
        exit 1
    fi
done
(( check_seconds >= 5 )) || check_seconds=5
(( reload_cooldown >= 60 )) || reload_cooldown=60

log_message() {
    local message="$1"
    printf '%s %s\n' "$(date --iso-8601=seconds)" "$message"
    logger -t nvgs-ethernet-watchdog -- "$message" 2>/dev/null || true
}

interface_type() {
    local candidate="$1"
    local detected=""
    if command -v nmcli >/dev/null 2>&1; then
        detected="$(
            nmcli -g GENERAL.TYPE device show "$candidate" 2>/dev/null \
                | head -n 1 \
                || true
        )"
    fi
    if [[ "$detected" == "ethernet" ]] \
        || { [[ -z "$detected" ]] \
            && [[ "$candidate" == en* || "$candidate" == eth* ]]; }; then
        printf 'ethernet\n'
    else
        printf '%s\n' "${detected:-other}"
    fi
}

detect_interface() {
    local candidate
    if [[ -n "$configured_interface" ]] \
        && [[ -d "/sys/class/net/$configured_interface" ]] \
        && [[ "$(interface_type "$configured_interface")" == "ethernet" ]]; then
        printf '%s\n' "$configured_interface"
        return 0
    fi

    if command -v nmcli >/dev/null 2>&1; then
        while IFS=: read -r candidate candidate_type _state; do
            if [[ "$candidate_type" == "ethernet" ]] \
                && [[ -d "/sys/class/net/$candidate" ]]; then
                printf '%s\n' "$candidate"
                return 0
            fi
        done < <(nmcli -t -f DEVICE,TYPE,STATE device status 2>/dev/null || true)
    fi

    for candidate_path in /sys/class/net/en* /sys/class/net/eth*; do
        if [[ -d "$candidate_path" ]]; then
            basename "$candidate_path"
            return 0
        fi
    done
    return 1
}

has_carrier() {
    [[ "$(cat "/sys/class/net/$1/carrier" 2>/dev/null || true)" == "1" ]]
}

has_ipv4() {
    ip -4 -o address show dev "$1" scope global 2>/dev/null | grep -q .
}

set_full_power() {
    local candidate="$1"
    local power_control="/sys/class/net/$candidate/device/power/control"
    if [[ "$prevent_runtime_pm" == "true" && -w "$power_control" ]]; then
        if [[ "$(cat "$power_control" 2>/dev/null || true)" != "on" ]]; then
            printf 'on\n' > "$power_control" 2>/dev/null || true
            log_message "$candidate: disabled PCI runtime power management."
        fi
    fi
}

disable_energy_efficient_ethernet() {
    local candidate="$1"
    if [[ "$disable_eee" != "true" ]] \
        || ! command -v ethtool >/dev/null 2>&1; then
        return 0
    fi
    if ethtool --show-eee "$candidate" >/dev/null 2>&1; then
        if ethtool --set-eee "$candidate" eee off >/dev/null 2>&1; then
            log_message "$candidate: Energy Efficient Ethernet is disabled."
        fi
    fi
}

activate_saved_connection() {
    local candidate="$1"
    if ! command -v nmcli >/dev/null 2>&1 \
        || ! systemctl is-active --quiet NetworkManager.service; then
        return 1
    fi
    nmcli networking on >/dev/null 2>&1 || true
    nmcli --wait 15 connection up ifname "$candidate" >/dev/null 2>&1 || true
}

wait_for_carrier() {
    local candidate="$1"
    local attempts="${2:-8}"
    local attempt
    for ((attempt = 0; attempt < attempts; attempt++)); do
        if [[ -d "/sys/class/net/$candidate" ]] && has_carrier "$candidate"; then
            return 0
        fi
        sleep 1
    done
    return 1
}

cycle_link() {
    local candidate="$1"
    log_message "$candidate: cycling the Ethernet interface."
    ip link set dev "$candidate" down >/dev/null 2>&1 || true
    sleep 1
    ip link set dev "$candidate" up >/dev/null 2>&1 || true
    activate_saved_connection "$candidate" || true
    wait_for_carrier "$candidate" 8
}

driver_module() {
    local module_path
    module_path="$(
        readlink -f "/sys/class/net/$1/device/driver/module" 2>/dev/null \
            || true
    )"
    [[ -n "$module_path" ]] && basename "$module_path"
}

driver_has_another_live_interface() {
    local driver="$1"
    local excluded="$2"
    local candidate_path
    local candidate
    for candidate_path in /sys/class/net/*; do
        [[ -d "$candidate_path" ]] || continue
        candidate="$(basename "$candidate_path")"
        [[ "$candidate" != "$excluded" ]] || continue
        if [[ "$(driver_module "$candidate")" == "$driver" ]] \
            && { has_carrier "$candidate" || has_ipv4 "$candidate"; }; then
            return 0
        fi
    done
    return 1
}

reload_verified_driver() {
    local candidate="$1"
    local driver
    local pci_path
    local pci_address
    local replacement
    driver="$(driver_module "$candidate")"
    if [[ "$driver" != "r8169" ]]; then
        log_message "$candidate: refusing automatic reload of unapproved driver '${driver:-unknown}'."
        return 1
    fi
    if driver_has_another_live_interface "$driver" "$candidate"; then
        log_message "$candidate: $driver also controls a live interface; reload skipped."
        return 1
    fi

    pci_path="$(readlink -f "/sys/class/net/$candidate/device" 2>/dev/null || true)"
    pci_address="$(basename "$pci_path")"
    log_message "$candidate: reloading verified Realtek driver $driver ($pci_address)."
    ip link set dev "$candidate" down >/dev/null 2>&1 || true
    if ! modprobe -r "$driver"; then
        log_message "$candidate: $driver could not be unloaded."
        return 1
    fi
    sleep 2
    if ! modprobe "$driver"; then
        log_message "$candidate: $driver could not be loaded again."
        return 1
    fi
    command -v udevadm >/dev/null 2>&1 \
        && udevadm settle --timeout=10 >/dev/null 2>&1 \
        || true

    replacement=""
    if [[ -n "$pci_path" && -d "$pci_path/net" ]]; then
        for replacement_path in "$pci_path"/net/*; do
            if [[ -d "$replacement_path" ]]; then
                replacement="$(basename "$replacement_path")"
                break
            fi
        done
    fi
    if [[ -z "$replacement" ]]; then
        replacement="$(detect_interface || true)"
    fi
    if [[ -z "$replacement" || ! -d "/sys/class/net/$replacement" ]]; then
        log_message "$pci_address: Ethernet interface did not return after reloading $driver."
        return 1
    fi

    configured_interface="$replacement"
    set_full_power "$replacement"
    disable_energy_efficient_ethernet "$replacement"
    ip link set dev "$replacement" up >/dev/null 2>&1 || true
    activate_saved_connection "$replacement" || true
    wait_for_carrier "$replacement" 12
}

exec 9> /run/lock/nvgs-ethernet-recovery.lock
driver_reloads=0
last_reload_epoch=0
ever_had_carrier=false
consecutive_down=0
policy_interface=""

attempt_recovery() {
    local candidate="$1"
    local force_reload="$2"
    local now
    local -a lock_command

    if [[ "$force_reload" == "true" ]]; then
        lock_command=(flock -w 45 9)
    else
        lock_command=(flock -n 9)
    fi
    if ! "${lock_command[@]}"; then
        log_message "$candidate: another Ethernet recovery is already running."
        return 1
    fi

    set_full_power "$candidate"
    disable_energy_efficient_ethernet "$candidate"
    if cycle_link "$candidate"; then
        flock -u 9
        return 0
    fi

    now="$(date +%s)"
    if [[ "$force_reload" == "true" ]] \
        || { (( consecutive_down >= 2 )) \
            && (( driver_reloads < max_reloads )) \
            && (( now - last_reload_epoch >= reload_cooldown )); }; then
        last_reload_epoch="$now"
        driver_reloads=$((driver_reloads + 1))
        if reload_verified_driver "$candidate"; then
            flock -u 9
            return 0
        fi
    fi

    flock -u 9
    return 1
}

check_once() {
    local force_reload="$1"
    local candidate
    candidate="$(detect_interface || true)"
    if [[ -z "$candidate" ]]; then
        log_message "No Ethernet interface is visible to Ubuntu."
        return 1
    fi
    if has_carrier "$candidate"; then
        set_full_power "$candidate"
        disable_energy_efficient_ethernet "$candidate"
        activate_saved_connection "$candidate" || true
        log_message "$candidate: Ethernet carrier is present."
        return 0
    fi
    consecutive_down=$((consecutive_down + 1))
    attempt_recovery "$candidate" "$force_reload"
}

if [[ "$mode" == "--once" ]]; then
    if check_once "$force_driver_reload"; then
        exit 0
    fi
    exit 2
fi

log_message "Automatic Ethernet recovery started."
while true; do
    interface="$(detect_interface || true)"
    if [[ -z "$interface" ]]; then
        if (( consecutive_down == 0 || consecutive_down % 4 == 0 )); then
            log_message "No Ethernet interface is visible; waiting for the device to return."
        fi
        consecutive_down=$((consecutive_down + 1))
        sleep "$check_seconds"
        continue
    fi

    if [[ "$policy_interface" != "$interface" ]]; then
        set_full_power "$interface"
        disable_energy_efficient_ethernet "$interface"
        policy_interface="$interface"
    fi

    if has_carrier "$interface"; then
        if [[ "$ever_had_carrier" == "false" || "$consecutive_down" -gt 0 ]]; then
            log_message "$interface: Ethernet link is connected."
        fi
        ever_had_carrier=true
        consecutive_down=0
        driver_reloads=0
        if ! has_ipv4 "$interface"; then
            activate_saved_connection "$interface" || true
        fi
    else
        consecutive_down=$((consecutive_down + 1))
        if (( consecutive_down <= 2 || consecutive_down % 4 == 0 )); then
            if attempt_recovery "$interface" "false"; then
                log_message "$interface: Ethernet recovered automatically."
                ever_had_carrier=true
                consecutive_down=0
                driver_reloads=0
            elif (( consecutive_down == 2 )); then
                log_message "$interface: recovery failed; cable/port or a cold power reset may be required."
            fi
        fi
    fi
    sleep "$check_seconds"
done
