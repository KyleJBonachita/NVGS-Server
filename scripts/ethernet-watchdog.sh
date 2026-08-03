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
configured_pci_address="${NVGS_ETHERNET_PCI_ADDRESS:-}"
configured_pci_vendor="${NVGS_ETHERNET_PCI_VENDOR:-}"
configured_pci_device="${NVGS_ETHERNET_PCI_DEVICE:-}"
configured_driver="${NVGS_ETHERNET_DRIVER:-}"
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

is_physical_ethernet_interface() {
    local candidate="$1"
    [[ -n "$candidate" && -d "/sys/class/net/$candidate" ]] || return 1
    case "$candidate" in
        lo|docker*|br-*|veth*|virbr*|podman*|tailscale*) return 1 ;;
    esac
    [[ -e "/sys/class/net/$candidate/device" ]] || return 1
    [[ "$(interface_type "$candidate")" == "ethernet" ]]
}

pci_address_for_interface() {
    local candidate="$1"
    local device_path
    device_path="$(
        readlink -f "/sys/class/net/$candidate/device" 2>/dev/null || true
    )"
    if [[ "$(basename "$device_path")" =~ ^[0-9a-fA-F]{4}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.[0-7]$ ]]; then
        basename "$device_path"
    fi
}

interface_for_pci() {
    local pci_address="$1"
    local candidate_path
    local candidate
    for candidate_path in "/sys/bus/pci/devices/$pci_address"/net/*; do
        [[ -d "$candidate_path" ]] || continue
        candidate="$(basename "$candidate_path")"
        if is_physical_ethernet_interface "$candidate"; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done
    return 1
}

detect_interface() {
    local candidate
    if is_physical_ethernet_interface "$configured_interface"; then
        printf '%s\n' "$configured_interface"
        return 0
    fi

    if [[ -n "$configured_pci_address" ]]; then
        candidate="$(interface_for_pci "$configured_pci_address" || true)"
        if [[ -n "$candidate" ]]; then
            printf '%s\n' "$candidate"
            return 0
        fi
    fi

    if command -v nmcli >/dev/null 2>&1; then
        while IFS=: read -r candidate candidate_type _state; do
            if [[ "$candidate_type" == "ethernet" ]] \
                && is_physical_ethernet_interface "$candidate"; then
                printf '%s\n' "$candidate"
                return 0
            fi
        done < <(nmcli -t -f DEVICE,TYPE,STATE device status 2>/dev/null || true)
    fi

    for candidate_path in /sys/class/net/en* /sys/class/net/eth*; do
        [[ -d "$candidate_path" ]] || continue
        candidate="$(basename "$candidate_path")"
        if is_physical_ethernet_interface "$candidate"; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done
    return 1
}

has_carrier() {
    is_physical_ethernet_interface "$1" \
        && [[ "$(cat "/sys/class/net/$1/carrier" 2>/dev/null || true)" == "1" ]]
}

has_ipv4() {
    ip -4 -o address show dev "$1" scope global 2>/dev/null | grep -q .
}

normalize_hex() {
    printf '%s\n' "${1,,}" | sed 's/^0x/0x/'
}

pci_identity_matches() {
    local pci_address="$1"
    local pci_path="/sys/bus/pci/devices/$pci_address"
    local actual_vendor
    local actual_device
    local actual_class
    [[ "$pci_address" =~ ^[0-9a-fA-F]{4}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.[0-7]$ ]] \
        || return 1
    [[ -d "$pci_path" ]] || return 1
    [[ -n "$configured_pci_address" \
        && "${pci_address,,}" == "${configured_pci_address,,}" ]] || return 1
    [[ -n "$configured_pci_vendor" && -n "$configured_pci_device" ]] || return 1
    [[ "$configured_driver" == "r8169" ]] || return 1
    actual_vendor="$(cat "$pci_path/vendor" 2>/dev/null || true)"
    actual_device="$(cat "$pci_path/device" 2>/dev/null || true)"
    actual_class="$(cat "$pci_path/class" 2>/dev/null || true)"
    [[ "$(normalize_hex "$actual_vendor")" == "$(normalize_hex "$configured_pci_vendor")" \
        && "$(normalize_hex "$actual_device")" == "$(normalize_hex "$configured_pci_device")" \
        && "${actual_class,,}" == 0x0200* ]]
}

set_pci_path_full_power() {
    local pci_address="$1"
    local current_path
    local changed=false
    [[ "$prevent_runtime_pm" == "true" ]] || return 0
    current_path="$(
        readlink -f "/sys/bus/pci/devices/$pci_address" 2>/dev/null || true
    )"
    while [[ -n "$current_path" && "$current_path" == /sys/devices/* ]]; do
        if [[ -w "$current_path/power/control" ]] \
            && [[ "$(cat "$current_path/power/control" 2>/dev/null || true)" != "on" ]]; then
            printf 'on\n' > "$current_path/power/control" 2>/dev/null || true
            changed=true
        fi
        [[ "$current_path" != "/sys/devices" ]] || break
        current_path="$(dirname "$current_path")"
    done
    if [[ "$changed" == "true" ]]; then
        log_message "$pci_address: disabled runtime power management along its PCI path."
    fi
}

set_full_power() {
    local candidate="$1"
    local pci_address
    pci_address="$(pci_address_for_interface "$candidate")"
    if [[ -n "$pci_address" ]]; then
        set_pci_path_full_power "$pci_address"
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
        if has_carrier "$candidate"; then
            return 0
        fi
        sleep 1
    done
    return 1
}

bring_up_and_verify() {
    local candidate="$1"
    is_physical_ethernet_interface "$candidate" || return 1
    configured_interface="$candidate"
    set_full_power "$candidate"
    disable_energy_efficient_ethernet "$candidate"
    ip link set dev "$candidate" up >/dev/null 2>&1 || true
    activate_saved_connection "$candidate" || true
    wait_for_carrier "$candidate" 12
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
        if is_physical_ethernet_interface "$candidate" \
            && [[ "$(driver_module "$candidate")" == "$driver" ]] \
            && { has_carrier "$candidate" || has_ipv4 "$candidate"; }; then
            return 0
        fi
    done
    return 1
}

settle_devices() {
    command -v udevadm >/dev/null 2>&1 \
        && udevadm settle --timeout=10 >/dev/null 2>&1 \
        || true
}

recover_verified_pci_device() {
    local pci_address="$1"
    local pci_path="/sys/bus/pci/devices/$pci_address"
    local real_path
    local parent_rescan
    local replacement
    local attempt

    if ! pci_identity_matches "$pci_address"; then
        log_message "${pci_address:-unknown}: PCI recovery refused because its stored identity could not be verified."
        return 1
    fi
    set_pci_path_full_power "$pci_address"

    if [[ -w "$pci_path/reset" ]]; then
        log_message "$pci_address: attempting a verified PCI function reset."
        modprobe -r r8169 >/dev/null 2>&1 || true
        if printf '1\n' > "$pci_path/reset" 2>/dev/null; then
            sleep 2
            modprobe r8169 >/dev/null 2>&1 || true
            settle_devices
            replacement="$(interface_for_pci "$pci_address" || true)"
            if [[ -n "$replacement" ]] && bring_up_and_verify "$replacement"; then
                return 0
            fi
        fi
    fi

    if ! pci_identity_matches "$pci_address"; then
        return 1
    fi
    real_path="$(readlink -f "$pci_path" 2>/dev/null || true)"
    parent_rescan="$(dirname "$real_path")/rescan"
    if [[ ! -w "$pci_path/remove" ]]; then
        log_message "$pci_address: PCI hot-remove is unavailable; a cold power reset may be required."
        return 1
    fi
    if [[ ! -w "$parent_rescan" && ! -w /sys/bus/pci/rescan ]]; then
        log_message "$pci_address: PCI rescan control is unavailable."
        return 1
    fi

    log_message "$pci_address: hot-removing and rescanning the verified Realtek adapter."
    modprobe -r r8169 >/dev/null 2>&1 || true
    printf '1\n' > "$pci_path/remove" 2>/dev/null || return 1
    sleep 2
    if [[ -w "$parent_rescan" ]]; then
        printf '1\n' > "$parent_rescan" 2>/dev/null || true
    else
        printf '1\n' > /sys/bus/pci/rescan 2>/dev/null || true
    fi
    for ((attempt = 0; attempt < 8; attempt++)); do
        [[ -d "$pci_path" ]] && break
        sleep 1
    done
    if ! pci_identity_matches "$pci_address"; then
        log_message "$pci_address: adapter did not reappear after its PCI rescan."
        return 1
    fi
    set_pci_path_full_power "$pci_address"
    modprobe r8169 >/dev/null 2>&1 || true
    settle_devices
    replacement="$(interface_for_pci "$pci_address" || true)"
    if [[ -z "$replacement" ]]; then
        log_message "$pci_address: r8169 still could not create a physical Ethernet interface."
        return 1
    fi
    bring_up_and_verify "$replacement"
}

reload_verified_driver() {
    local candidate="$1"
    local driver
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

    pci_address="$(pci_address_for_interface "$candidate")"
    if ! pci_identity_matches "$pci_address"; then
        log_message "$candidate: driver reload refused because the PCI identity is not the installed adapter."
        return 1
    fi
    log_message "$candidate: reloading verified Realtek driver $driver ($pci_address)."
    ip link set dev "$candidate" down >/dev/null 2>&1 || true
    if ! modprobe -r "$driver"; then
        log_message "$candidate: $driver could not be unloaded."
        return 1
    fi
    sleep 2
    modprobe "$driver" >/dev/null 2>&1 || true
    settle_devices

    replacement="$(interface_for_pci "$pci_address" || true)"
    if [[ -n "$replacement" ]] && bring_up_and_verify "$replacement"; then
        return 0
    fi
    log_message "$pci_address: normal r8169 reload failed; escalating to verified PCI recovery."
    recover_verified_pci_device "$pci_address"
}

exec 9> /run/lock/nvgs-ethernet-recovery.lock
driver_reloads=0
last_reload_epoch=0
ever_had_carrier=false
consecutive_down=0
policy_interface=""

reload_allowed() {
    local force_reload="$1"
    local now
    now="$(date +%s)"
    [[ "$force_reload" == "true" ]] \
        || { (( consecutive_down >= 2 )) \
            && (( driver_reloads < max_reloads )) \
            && (( now - last_reload_epoch >= reload_cooldown )); }
}

record_reload_attempt() {
    last_reload_epoch="$(date +%s)"
    driver_reloads=$((driver_reloads + 1))
}

attempt_recovery() {
    local candidate="$1"
    local force_reload="$2"
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

    if reload_allowed "$force_reload"; then
        record_reload_attempt
        if reload_verified_driver "$candidate"; then
            flock -u 9
            return 0
        fi
    fi

    flock -u 9
    return 1
}

attempt_missing_device_recovery() {
    local force_reload="$1"
    local replacement
    local -a lock_command
    if [[ "$force_reload" == "true" ]]; then
        lock_command=(flock -w 45 9)
    else
        lock_command=(flock -n 9)
    fi
    reload_allowed "$force_reload" || return 1
    if ! "${lock_command[@]}"; then
        return 1
    fi
    record_reload_attempt
    if recover_verified_pci_device "$configured_pci_address"; then
        replacement="$(interface_for_pci "$configured_pci_address" || true)"
        configured_interface="$replacement"
        flock -u 9
        return 0
    fi
    flock -u 9
    return 1
}

check_once() {
    local force_reload="$1"
    local candidate
    candidate="$(detect_interface || true)"
    if [[ -z "$candidate" ]]; then
        consecutive_down=$((consecutive_down + 1))
        log_message "No physical Ethernet interface is visible to Ubuntu."
        attempt_missing_device_recovery "$force_reload"
        return $?
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
        consecutive_down=$((consecutive_down + 1))
        if (( consecutive_down <= 2 || consecutive_down % 4 == 0 )); then
            log_message "No physical Ethernet interface is visible; attempting verified device recovery."
        fi
        if (( consecutive_down == 2 || consecutive_down % 4 == 0 )) \
            && attempt_missing_device_recovery "false"; then
            log_message "$configured_interface: physical Ethernet recovered automatically."
            ever_had_carrier=true
            consecutive_down=0
            driver_reloads=0
        fi
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
                log_message "$configured_interface: physical Ethernet recovered automatically."
                ever_had_carrier=true
                consecutive_down=0
                driver_reloads=0
            elif (( consecutive_down == 2 )); then
                log_message "$interface: recovery failed; the adapter may require a cold power reset."
            fi
        fi
    fi
    sleep "$check_seconds"
done
