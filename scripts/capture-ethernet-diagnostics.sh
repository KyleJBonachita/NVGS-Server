#!/usr/bin/env bash
set -u

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

output_file="$project_dir/UBUNTU_NETWORK_ERROR.md"

read_watchdog_value() {
    local key="$1"
    if [[ -f /etc/nvgs-ethernet-watchdog.env ]]; then
        sed -n "s/^[[:space:]]*${key}[[:space:]]*=[[:space:]]*//p" \
            /etc/nvgs-ethernet-watchdog.env \
            | tail -n 1 \
            | tr -d '\r'
    fi
}

is_physical_ethernet_interface() {
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

interface="$(read_watchdog_value "NVGS_ETHERNET_INTERFACE")"
if ! is_physical_ethernet_interface "$interface"; then
    interface=""
fi
if [[ -z "$interface" ]] && command -v nmcli >/dev/null 2>&1; then
    while IFS=: read -r candidate candidate_type _state; do
        if [[ "$candidate_type" == "ethernet" ]] \
            && is_physical_ethernet_interface "$candidate"; then
            interface="$candidate"
            break
        fi
    done < <(nmcli -t -f DEVICE,TYPE,STATE device status 2>/dev/null || true)
fi

pci_address="$(read_watchdog_value "NVGS_ETHERNET_PCI_ADDRESS")"
if [[ -n "$interface" ]]; then
    pci_path="$(
        readlink -f "/sys/class/net/$interface/device" 2>/dev/null || true
    )"
    interface_pci="$(basename "$pci_path")"
    if [[ "$interface_pci" =~ ^[0-9a-fA-F]{4}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.[0-7]$ ]]; then
        pci_address="$interface_pci"
    fi
fi
if [[ ! "$pci_address" =~ ^[0-9a-fA-F]{4}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.[0-7]$ ]]; then
    pci_address=""
fi
if [[ -z "$pci_address" ]]; then
    for candidate_path in /sys/bus/pci/devices/*; do
        [[ -d "$candidate_path" ]] || continue
        if [[ "$(cat "$candidate_path/vendor" 2>/dev/null || true)" == "0x10ec" \
            && "$(cat "$candidate_path/device" 2>/dev/null || true)" == "0x3000" ]]; then
            pci_address="$(basename "$candidate_path")"
            break
        fi
    done
fi

echo "Collecting Ethernet diagnostics for ${interface:-missing physical interface}..."
echo "Ubuntu may ask for your password once."
sudo -v

{
    echo "# Ubuntu Ethernet recovery diagnostics"
    echo
    echo "Captured: $(date --iso-8601=seconds)"
    echo "Physical interface: ${interface:-not visible}"
    echo "PCI address: ${pci_address:-not visible}"
    echo "Recorded driver: $(read_watchdog_value "NVGS_ETHERNET_DRIVER")"
    echo
    echo "## Watchdog configuration"
    sudo sed -E \
        's/^([^#[:space:]][^=]*)=.*/\1=<configured>/' \
        /etc/nvgs-ethernet-watchdog.env 2>/dev/null \
        || echo "Watchdog environment is unavailable."
    echo
    echo "## Watchdog status"
    systemctl status nvgs-ethernet-watchdog.service --no-pager || true
    echo
    echo "## Watchdog journal"
    sudo journalctl \
        -u nvgs-ethernet-watchdog.service \
        -b \
        --no-pager \
        || true
    echo
    echo "## Relevant kernel journal"
    sudo journalctl -k -b --no-pager 2>/dev/null \
        | grep -Ei "r8169|${interface:-enp109s0}|${pci_address:-0000:6d:00.0}|RTL8125|RTL8226|D3cold|PCI read failed|phy_poll_reset|rtl_ocp_gphy_cond" \
        || true
    echo
    echo "## Interfaces"
    ip -brief link 2>/dev/null || true
    ip -4 -brief address 2>/dev/null || true
    if command -v nmcli >/dev/null 2>&1; then
        nmcli -f DEVICE,TYPE,STATE,CONNECTION device status 2>/dev/null || true
    fi
    echo
    echo "## Physical interface and EEE"
    if [[ -n "$interface" ]] && command -v ethtool >/dev/null 2>&1; then
        sudo ethtool "$interface" || true
        sudo ethtool --show-eee "$interface" || true
    elif [[ -z "$interface" ]]; then
        echo "No physical Ethernet interface exists; ethtool was skipped."
    else
        echo "ethtool is not installed."
    fi
    echo
    echo "## PCI device"
    if [[ -n "$pci_address" && -d "/sys/bus/pci/devices/$pci_address" ]]; then
        pci_path="/sys/bus/pci/devices/$pci_address"
        echo "Vendor: $(cat "$pci_path/vendor" 2>/dev/null || echo unavailable)"
        echo "Device: $(cat "$pci_path/device" 2>/dev/null || echo unavailable)"
        echo "Class: $(cat "$pci_path/class" 2>/dev/null || echo unavailable)"
        echo "Runtime status: $(cat "$pci_path/power/runtime_status" 2>/dev/null || echo unavailable)"
        echo "Runtime control: $(cat "$pci_path/power/control" 2>/dev/null || echo unavailable)"
        echo "Function reset: $(test -w "$pci_path/reset" && echo writable || echo unavailable)"
        echo "Hot-remove: $(test -w "$pci_path/remove" && echo writable || echo unavailable)"
        if command -v lspci >/dev/null 2>&1; then
            sudo lspci -s "$pci_address" -vvnnk || true
            echo
            sudo lspci -tv || true
        fi
    else
        echo "The configured Ethernet PCI device is unavailable."
    fi
} > "$output_file" 2>&1

echo
echo "Saved: $output_file"
echo "Send it with:"
echo "  git add UBUNTU_NETWORK_ERROR.md"
echo "  git commit -m \"Update Ethernet watchdog error\""
echo "  git push origin main"
