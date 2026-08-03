#!/usr/bin/env bash
set -u

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

echo "NVGS SERVER HUB - NETWORK RECOVERY"
echo
set +e
"$project_dir/scripts/ensure-lan-ready.sh" --require-ethernet
status="$?"
set -e

if [[ "$status" -ne 0 ]]; then
    echo
    echo "Starting privileged Ethernet hardware recovery..."
    recovery_helper="/usr/local/libexec/nvgs-ethernet-watchdog"
    if [[ ! -x "$recovery_helper" ]]; then
        recovery_helper="$project_dir/scripts/ethernet-watchdog.sh"
    fi
    set +e
    sudo -- "$recovery_helper" --once --force-driver-reload
    recovery_status="$?"
    set -e
    if [[ "$recovery_status" -eq 0 ]]; then
        sleep 2
        set +e
        "$project_dir/scripts/ensure-lan-ready.sh" --require-ethernet
        status="$?"
        set -e
    fi
fi
echo
if [[ "$status" -eq 0 ]]; then
    echo "Ethernet recovery completed successfully."
else
    echo "Automatic recovery could not restore Ethernet. Wi-Fi was not disabled."
fi
echo "Press Enter to close."
read -r _
exit "$status"
