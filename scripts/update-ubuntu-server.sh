#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

if [[ -n "$(git status --porcelain)" ]]; then
    echo "Update stopped because tracked files were changed on Ubuntu." >&2
    echo "Keep code changes on Windows, commit/push them, then pull here." >&2
    echo "Run 'git status' to inspect the Ubuntu changes." >&2
    exit 1
fi

echo "1/6 Backing up the current ticket database..."
./scripts/backup.sh

echo "2/6 Downloading the latest code from GitHub..."
git pull --ff-only

echo "3/6 Checking local secret files..."
./scripts/bootstrap-secrets.sh

if grep -q \
    '^[[:space:]]*APPSCRIPT_SSO_SUCCESS_REDIRECT[[:space:]]*=[[:space:]]*/api/auth/me/[[:space:]]*$' \
    .env; then
    sed -i \
        's|^[[:space:]]*APPSCRIPT_SSO_SUCCESS_REDIRECT[[:space:]]*=.*|APPSCRIPT_SSO_SUCCESS_REDIRECT=/tickets/|' \
        .env
    echo "Updated the successful login destination to the ticket dashboard."
fi

echo "4/6 Downloading updated server images..."
docker compose pull

echo "5/6 Rebuilding and restarting the application..."
docker compose up -d --build --remove-orphans

echo "6/6 Refreshing the selected Ubuntu server mode..."
sudo ./scripts/install-ubuntu-host.sh

docker compose ps

echo
echo "Update complete. The pre-update database backup is under backups/."
if grep -q '^[[:space:]]*NVGS_HOST_MODE[[:space:]]*=[[:space:]]*on_demand' .env; then
    echo "NVGS remains controlled by the open 'NVGS Server Control' window."
    echo "Close and reopen that controller now to activate launcher updates."
fi
