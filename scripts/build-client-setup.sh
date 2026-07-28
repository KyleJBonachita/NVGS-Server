#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

if [[ "${EUID}" -eq 0 ]]; then
    echo "Run this from your normal Ubuntu account, without sudo." >&2
    exit 1
fi
if [[ ! -f .env ]]; then
    echo "Missing .env. Start with ./scripts/bootstrap-secrets.sh." >&2
    exit 1
fi

server_name="$(
    sed -n \
        's/^[[:space:]]*NVGS_LAN_SERVER_NAME[[:space:]]*=[[:space:]]*//p' \
        .env |
        tail -n 1 |
        tr -d '\r"'
)"
if [[ -z "$server_name" ]]; then
    echo "A stable client hostname is not configured." >&2
    echo "Configure it first, for example:" >&2
    echo "  ./scripts/refresh-dynamic-lan.sh enp109s0 ticketing-system.local" >&2
    exit 1
fi

./scripts/export-client-ca.sh
python3 ./scripts/build_client_setup.py
