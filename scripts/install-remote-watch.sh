#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat <<'EOF'
Run this on a SECOND approved Ubuntu device, not on the NVGS server:

  sudo ./scripts/install-remote-watch.sh \
    https://ASSIGNED_SERVER_ADDRESS/api/health/ \
    /path/to/nvgs-local-ca.crt

After installation, add an approved webhook to /etc/nvgs-remote-watch.env.
EOF
}

if [[ "${EUID}" -ne 0 ]]; then
    usage >&2
    exit 1
fi
if [[ "$#" -ne 2 ]]; then
    usage >&2
    exit 1
fi

health_url="$1"
ca_file="$(realpath "$2")"
if [[ ! "$health_url" =~ ^https://[^/]+/api/health/$ ]]; then
    echo "Use the complete HTTPS health address ending in /api/health/." >&2
    exit 1
fi
if [[ "$health_url" =~ https://(localhost|127[.]0[.]0[.]1|\[::1\])/ ]]; then
    echo "Use the NVGS server's approved LAN address, not localhost." >&2
    exit 1
fi
if [[ ! -s "$ca_file" ]]; then
    echo "The public NVGS CA certificate was not found: $ca_file" >&2
    exit 1
fi

install -d -m 0755 /usr/local/lib/nvgs
install -m 0755 host/nvgs_remote_watch.py /usr/local/lib/nvgs/
install -m 0644 "$ca_file" /usr/local/lib/nvgs/nvgs-local-ca.crt
install -m 0644 \
    host/systemd/nvgs-remote-watch.service \
    /etc/systemd/system/nvgs-remote-watch.service

if [[ ! -f /etc/nvgs-remote-watch.env ]]; then
    {
        echo "NVGS_REMOTE_SERVER_NAME=NVGS-Server"
        echo "NVGS_REMOTE_HEALTH_URL=${health_url}"
        echo "NVGS_REMOTE_CA_FILE=/usr/local/lib/nvgs/nvgs-local-ca.crt"
        echo "NVGS_REMOTE_INTERVAL_SECONDS=30"
        echo "NVGS_REMOTE_TIMEOUT_SECONDS=8"
        echo "NVGS_REMOTE_FAILURE_THRESHOLD=3"
        echo "NVGS_REMOTE_REMINDER_SECONDS=1800"
        echo "NVGS_REMOTE_WEBHOOK_URL="
    } > /etc/nvgs-remote-watch.env
else
    sed -i \
        "s|^NVGS_REMOTE_HEALTH_URL=.*|NVGS_REMOTE_HEALTH_URL=${health_url}|" \
        /etc/nvgs-remote-watch.env
    sed -i \
        's|^NVGS_REMOTE_CA_FILE=.*|NVGS_REMOTE_CA_FILE=/usr/local/lib/nvgs/nvgs-local-ca.crt|' \
        /etc/nvgs-remote-watch.env
fi
chmod 0600 /etc/nvgs-remote-watch.env

systemctl daemon-reload
systemctl enable --now nvgs-remote-watch.service

echo
echo "External watcher installed on this second device."
echo "Add the approved webhook:"
echo "  sudo nano /etc/nvgs-remote-watch.env"
echo "Set NVGS_REMOTE_WEBHOOK_URL, then run:"
echo "  sudo systemctl restart nvgs-remote-watch.service"
echo "  journalctl -u nvgs-remote-watch.service -f"
