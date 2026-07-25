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

if [[ -z "${NVGS_ALERT_WEBHOOK_URL:-}" ]]; then
    echo "NVGS_ALERT_WEBHOOK_URL is blank in /etc/nvgs-monitor.env." >&2
    exit 1
fi

python3 host/send_test_alert.py
echo "The webhook accepted the test alert."
