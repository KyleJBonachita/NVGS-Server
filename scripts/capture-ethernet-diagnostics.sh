#!/usr/bin/env bash
set -u

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

output_file="$project_dir/UBUNTU_NETWORK_ERROR.md"
interface=""
if [[ -f /etc/nvgs-ethernet-watchdog.env ]]; then
    interface="$(
        sed -n \
            's/^[[:space:]]*NVGS_ETHERNET_INTERFACE[[:space:]]*=[[:space:]]*//p' \
            /etc/nvgs-ethernet-watchdog.env \
            | tail -n 1 \
            | tr -d '\r'
    )"
fi
if [[ -z "$interface" ]] && command -v nmcli >/dev/null 2>&1; then
    interface="$(
        nmcli -t -f DEVICE,TYPE device status 2>/dev/null \
            | awk -F: '$2 == "ethernet" {print $1; exit}'
    )"
fi
interface="${interface:-enp109s0}"

echo "Collecting Ethernet diagnostics for $interface..."
echo "Ubuntu may ask for your password once."
sudo -v

{
    echo "# Ubuntu Ethernet recovery diagnostics"
    echo
    echo "Captured: $(date --iso-8601=seconds)"
    echo "Interface: $interface"
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
        | grep -Ei 'r8169|enp109s0|ethernet|pcie|aer|d3|link' \
        || true
    echo
    echo "## Interface and EEE"
    if command -v ethtool >/dev/null 2>&1; then
        sudo ethtool "$interface" || true
        sudo ethtool --show-eee "$interface" || true
    else
        echo "ethtool is not installed"
    fi
    echo
    echo "## PCI device"
    if [[ -e "/sys/class/net/$interface/device" ]]; then
        pci_path="$(readlink -f "/sys/class/net/$interface/device")"
        pci_address="$(basename "$pci_path")"
        echo "PCI address: $pci_address"
        if command -v lspci >/dev/null 2>&1; then
            sudo lspci -s "$pci_address" -vvnnk || true
        fi
        echo
        echo "Runtime power control:"
        cat "/sys/class/net/$interface/device/power/control" 2>/dev/null \
            || echo "unavailable"
        echo
        echo "Function-reset control:"
        ls -l "/sys/class/net/$interface/device/reset" 2>&1 || true
    else
        echo "The Ethernet PCI device path is unavailable."
    fi
} > "$output_file" 2>&1

echo
echo "Saved: $output_file"
echo "Send it with:"
echo "  git add UBUNTU_NETWORK_ERROR.md"
echo "  git commit -m \"Update Ethernet watchdog error\""
echo "  git push origin main"
