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
    case "$candidate" in
        lo|docker*|br-*|veth*|virbr*|podman*|tailscale*) return 1 ;;
    esac
    [[ -e "/sys/class/net/$candidate/device" ]] || return 1
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
    while IFS=: read -r candidate candidate_type _state; do
        if [[ "$candidate_type" == "ethernet" ]] \
            && is_ethernet_interface "$candidate"; then
            ethernet_interface="$candidate"
            break
        fi
    done < <(nmcli -t -f DEVICE,TYPE,STATE device status 2>/dev/null || true)
fi
if [[ -z "$ethernet_interface" ]]; then
    for candidate_path in /sys/class/net/en* /sys/class/net/eth*; do
        if [[ -d "$candidate_path" ]] \
            && is_ethernet_interface "$(basename "$candidate_path")"; then
            ethernet_interface="$(basename "$candidate_path")"
            break
        fi
    done
fi

existing_pci_address="$(read_existing_value "NVGS_ETHERNET_PCI_ADDRESS")"
existing_pci_vendor="$(read_existing_value "NVGS_ETHERNET_PCI_VENDOR")"
existing_pci_device="$(read_existing_value "NVGS_ETHERNET_PCI_DEVICE")"
existing_pci_driver="$(read_existing_value "NVGS_ETHERNET_DRIVER")"
pci_address=""
pci_vendor=""
pci_device=""
pci_driver=""

read_pci_identity() {
    local address="$1"
    local pci_path="/sys/bus/pci/devices/$address"
    local pci_class
    [[ "$address" =~ ^[0-9a-fA-F]{4}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.[0-7]$ ]] \
        || return 1
    [[ -d "$pci_path" ]] || return 1
    pci_class="$(cat "$pci_path/class" 2>/dev/null || true)"
    [[ "${pci_class,,}" == 0x0200* ]] || return 1
    pci_address="$address"
    pci_vendor="$(cat "$pci_path/vendor" 2>/dev/null || true)"
    pci_device="$(cat "$pci_path/device" 2>/dev/null || true)"
    pci_driver="$(
        basename "$(readlink -f "$pci_path/driver" 2>/dev/null || true)"
    )"
    [[ "$pci_vendor" =~ ^0x[0-9a-fA-F]{4}$ \
        && "$pci_device" =~ ^0x[0-9a-fA-F]{4}$ ]]
}

if [[ -n "$ethernet_interface" ]]; then
    interface_device_path="$(
        readlink -f "/sys/class/net/$ethernet_interface/device" 2>/dev/null \
            || true
    )"
    read_pci_identity "$(basename "$interface_device_path")" || true
fi

if [[ -z "$pci_address" \
    && "$existing_pci_address" =~ ^[0-9a-fA-F]{4}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.[0-7]$ \
    && -n "$existing_pci_vendor" && -n "$existing_pci_device" \
    && "$(cat "/sys/bus/pci/devices/$existing_pci_address/vendor" 2>/dev/null || true)" == "$existing_pci_vendor" \
    && "$(cat "/sys/bus/pci/devices/$existing_pci_address/device" 2>/dev/null || true)" == "$existing_pci_device" ]]; then
    read_pci_identity "$existing_pci_address" || true
    pci_driver="${pci_driver:-$existing_pci_driver}"
fi

if [[ -z "$pci_address" ]]; then
    pci_address=""
    pci_vendor=""
    pci_device=""
    pci_driver=""
    # Prefer the exact Realtek Killer E3000/RTL8125B found in the diagnostic.
    for candidate_path in /sys/bus/pci/devices/*; do
        [[ -d "$candidate_path" ]] || continue
        candidate_vendor="$(cat "$candidate_path/vendor" 2>/dev/null || true)"
        candidate_device="$(cat "$candidate_path/device" 2>/dev/null || true)"
        if [[ "${candidate_vendor,,}" == "0x10ec" \
            && "${candidate_device,,}" == "0x3000" ]]; then
            read_pci_identity "$(basename "$candidate_path")" || true
            pci_driver="${pci_driver:-r8169}"
            break
        fi
    done
fi

if [[ -z "$pci_address" ]]; then
    for candidate_path in /sys/bus/pci/devices/*; do
        [[ -d "$candidate_path" ]] || continue
        candidate_class="$(cat "$candidate_path/class" 2>/dev/null || true)"
        candidate_driver="$(
            basename "$(readlink -f "$candidate_path/driver" 2>/dev/null || true)"
        )"
        if [[ "${candidate_class,,}" == 0x0200* \
            && "$candidate_driver" == "r8169" ]]; then
            read_pci_identity "$(basename "$candidate_path")" || true
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
NVGS_ETHERNET_PCI_ADDRESS=${pci_address}
NVGS_ETHERNET_PCI_VENDOR=${pci_vendor}
NVGS_ETHERNET_PCI_DEVICE=${pci_device}
NVGS_ETHERNET_DRIVER=${pci_driver}
NVGS_ETHERNET_CHECK_SECONDS=${check_seconds:-15}
NVGS_ETHERNET_RELOAD_COOLDOWN_SECONDS=${reload_cooldown:-600}
NVGS_ETHERNET_MAX_DRIVER_RELOADS=${max_reloads:-1}
NVGS_ETHERNET_DISABLE_EEE=${disable_eee:-true}
NVGS_ETHERNET_PREVENT_RUNTIME_PM=${prevent_runtime_pm:-true}
EOF
chmod 0600 /etc/nvgs-ethernet-watchdog.env

if [[ -n "$pci_vendor" && -n "$pci_device" ]]; then
    install -d -m 0755 /etc/udev/rules.d
    cat > /etc/udev/rules.d/70-nvgs-ethernet-full-power.rules <<EOF
# Keep the installed Ethernet adapter out of PCI runtime suspend from first detection.
ACTION=="add", SUBSYSTEM=="pci", ATTR{vendor}=="${pci_vendor,,}", ATTR{device}=="${pci_device,,}", TEST=="power/control", ATTR{power/control}="on"
EOF
    chmod 0644 /etc/udev/rules.d/70-nvgs-ethernet-full-power.rules
    if command -v udevadm >/dev/null 2>&1; then
        udevadm control --reload-rules
    fi
fi

if ! command -v ethtool >/dev/null 2>&1; then
    echo "WARNING: ethtool is not installed; EEE control will be skipped." >&2
    echo "Install it with: sudo apt install ethtool" >&2
fi

systemctl daemon-reload
systemctl enable nvgs-ethernet-watchdog.service >/dev/null
systemctl restart nvgs-ethernet-watchdog.service

echo "Automatic Ethernet recovery installed for ${ethernet_interface:-auto-detection}."
if [[ -n "$pci_address" ]]; then
    echo "Verified PCI adapter: $pci_address ($pci_vendor:$pci_device, ${pci_driver:-driver unavailable})"
else
    echo "WARNING: no physical Ethernet PCI identity was found." >&2
    echo "PCI reset recovery will remain disabled until the installer sees it." >&2
fi
