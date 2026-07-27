#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
    echo "Run this test with sudo:" >&2
    echo "  sudo ./scripts/test-alert.sh" >&2
    exit 1
fi

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

if [[ ! -f /etc/nvgs-monitor.env ]]; then
    echo "Missing /etc/nvgs-monitor.env." >&2
    echo "Run sudo ./scripts/install-ubuntu-host.sh first." >&2
    exit 1
fi

set -a
source /etc/nvgs-monitor.env
set +a

if ! python3 host/send_test_alert.py; then
    echo "The alert test failed. Review the messages above." >&2
    echo "Also check: journalctl -u nvgs-monitor.service -n 50 --no-pager" >&2
    exit 1
fi
echo "The local test alert was sent."
if [[ -n "${NVGS_ALERT_WEBHOOK_URL:-}" ]]; then
    echo "The configured webhook also accepted it."
fi
