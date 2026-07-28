#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
bridge_name="${1:-appscript-bridge}"
case "$bridge_name" in
    appscript-bridge|appscript-notification-bridge)
        ;;
    *)
        echo "Choose appscript-bridge or appscript-notification-bridge." >&2
        exit 1
        ;;
esac
bridge_dir="$project_dir/$bridge_name"

if [[ "${EUID}" -eq 0 ]]; then
    echo "Run this from your normal Ubuntu account, without sudo." >&2
    exit 1
fi
if [[ ! -f "$bridge_dir/.clasp.json" ]]; then
    echo "Apps Script is not linked to clasp yet." >&2
    echo "Create $bridge_name/.clasp.json with the approved scriptId," >&2
    echo "then run: npx --yes @google/clasp login --no-localhost" >&2
    exit 1
fi
if ! command -v node >/dev/null 2>&1 || ! command -v npx >/dev/null 2>&1; then
    echo "Node.js and npx are required for optional Apps Script syncing." >&2
    exit 1
fi

cd "$bridge_dir"
echo "Showing the exact Apps Script files that will be replaced:"
npx --yes @google/clasp show-file-status
echo
read -r -p "Push these bridge files to the linked Apps Script project? [y/N] " answer
if [[ ! "$answer" =~ ^[Yy]$ ]]; then
    echo "Apps Script push cancelled."
    exit 2
fi

npx --yes @google/clasp push
echo
echo "Apps Script source was pushed."
echo "A deployed web-app version is separate. Update the existing deployment"
echo "only when the Apps Script source changed and after reviewing it."
