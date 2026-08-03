#!/usr/bin/env bash
set -u

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

echo "NVGS SERVER HUB - NETWORK RECOVERY"
echo
"$project_dir/scripts/ensure-lan-ready.sh" --require-ethernet
status="$?"
echo
if [[ "$status" -eq 0 ]]; then
    echo "Ethernet recovery completed successfully."
else
    echo "Automatic recovery could not restore Ethernet. Wi-Fi was not disabled."
fi
echo "Press Enter to close."
read -r _
exit "$status"
