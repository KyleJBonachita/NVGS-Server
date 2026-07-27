#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

umask 077
mkdir -p secrets backups

if [[ ! -f .env ]]; then
    cp .env.example .env
    echo "Created .env from .env.example."
fi

if [[ ! -s secrets/postgres_password ]]; then
    openssl rand -base64 48 > secrets/postgres_password
    echo "Created secrets/postgres_password."
fi

if [[ ! -s secrets/django_secret_key ]]; then
    openssl rand -base64 64 > secrets/django_secret_key
    echo "Created secrets/django_secret_key."
fi

if [[ ! -s secrets/appscript_bridge_secret ]]; then
    openssl rand -base64 48 > secrets/appscript_bridge_secret
    echo "Created secrets/appscript_bridge_secret."
fi

if [[ ! -e secrets/ticket_notification_webhook ]]; then
    : > secrets/ticket_notification_webhook
    echo "Created the disabled ticket-notification webhook file."
fi

chmod 600 \
    .env \
    secrets/postgres_password \
    secrets/django_secret_key \
    secrets/appscript_bridge_secret \
    secrets/ticket_notification_webhook

echo
echo "Secrets are ready. Review .env before starting the server."
