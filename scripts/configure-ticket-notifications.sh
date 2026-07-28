#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

if [[ "${EUID}" -eq 0 ]]; then
    echo "Run this from your normal Ubuntu account, without sudo." >&2
    exit 1
fi

# Compose declares every supported notification secret up front. Ensure that
# newly added optional secret files exist before asking Docker to mount them,
# even when the selected delivery mode does not use those files.
echo "Checking required local secret files..."
./scripts/bootstrap-secrets.sh

set_env_value() {
    local key="$1"
    local value="$2"
    local escaped_value
    escaped_value="${value//\\/\\\\}"
    escaped_value="${escaped_value//&/\\&}"
    escaped_value="${escaped_value//|/\\|}"
    if grep -q "^[[:space:]]*${key}[[:space:]]*=" .env; then
        sed -i \
            "s|^[[:space:]]*${key}[[:space:]]*=.*|${key}=${escaped_value}|" \
            .env
    else
        printf '\n%s=%s\n' "$key" "$value" >> .env
    fi
}

echo "NVGS ticket notification setup"
echo
echo "1) Disabled"
echo "2) HTTPS webhook"
echo "3) Email -> existing Power Automate -> Teams"
echo "4) Apps Script Gmail -> existing Power Automate -> Teams"
read -r -p "Choose 1, 2, 3, or 4: " mode

case "$mode" in
    1)
        set_env_value "TICKET_NOTIFICATION_DELIVERY_MODE" "disabled"
        echo "Ticket notifications are disabled."
        ;;
    2)
        read -r -p "Approved HTTPS webhook URL: " webhook_url
        python3 - "$webhook_url" <<'PY'
import sys
from urllib.parse import urlsplit

value = sys.argv[1]
parsed = urlsplit(value)
if (
    parsed.scheme != "https"
    or not parsed.hostname
    or parsed.username
    or parsed.password
):
    raise SystemExit("The webhook must be a complete HTTPS URL.")
PY
        umask 077
        printf '%s\n' "$webhook_url" > secrets/ticket_notification_webhook
        chmod 0644 secrets/ticket_notification_webhook
        set_env_value "TICKET_NOTIFICATION_DELIVERY_MODE" "webhook"
        echo "Webhook delivery is configured."
        ;;
    3)
        read -r -p "Inbox monitored by Power Automate: " email_to
        read -r -p "Approved SMTP relay host: " email_host
        read -r -p "SMTP port [587]: " email_port
        email_port="${email_port:-587}"
        read -r -p "SMTP service-account username: " email_user
        read -r -p "Approved From address [$email_user]: " from_email
        from_email="${from_email:-$email_user}"
        read -r -p "Power Automate/Teams target label [OpsGroupChat]: " target
        target="${target:-OpsGroupChat}"
        read -r -s -p "SMTP service-account password (hidden): " smtp_password
        echo

        python3 - "$email_to" "$email_host" "$email_port" "$from_email" <<'PY'
import sys

recipients, host, port, sender = sys.argv[1:]
addresses = [value.strip() for value in recipients.split(",") if value.strip()]
if not addresses or any("@" not in value or " " in value for value in addresses):
    raise SystemExit("Enter one or more comma-separated destination email addresses.")
if not host or any(character.isspace() for character in host):
    raise SystemExit("The SMTP relay host is invalid.")
try:
    parsed_port = int(port)
except ValueError as error:
    raise SystemExit("The SMTP port must be a number.") from error
if not 1 <= parsed_port <= 65535:
    raise SystemExit("The SMTP port must be between 1 and 65535.")
if "@" not in sender or " " in sender:
    raise SystemExit("The From address is invalid.")
PY
        umask 077
        printf '%s' "$smtp_password" > secrets/smtp_password
        unset smtp_password
        chmod 0644 secrets/smtp_password
        set_env_value "TICKET_NOTIFICATION_DELIVERY_MODE" "email"
        set_env_value "TICKET_NOTIFICATION_EMAIL_TO" "$email_to"
        set_env_value "TICKET_NOTIFICATION_EMAIL_TARGET_NAME" "$target"
        set_env_value "EMAIL_HOST" "$email_host"
        set_env_value "EMAIL_PORT" "$email_port"
        set_env_value "EMAIL_HOST_USER" "$email_user"
        set_env_value "EMAIL_USE_TLS" "true"
        set_env_value "EMAIL_USE_SSL" "false"
        set_env_value "DEFAULT_FROM_EMAIL" "$from_email"
        echo "Email delivery is configured."
        echo "Power Automate should filter subjects beginning with GRTKT_EVENT."
        ;;
    4)
        echo
        echo "Use the dedicated signed Apps Script setup:"
        echo "  ./scripts/appscript-notification-setup.sh prepare"
        echo "  See docs/APPSCRIPT_NOTIFICATION_BRIDGE.md"
        exit 0
        ;;
    *)
        echo "No changes made. Choose 1, 2, 3, or 4." >&2
        exit 2
        ;;
esac

chmod 0600 .env
echo
echo "Apply the setting with:"
echo "  docker compose up -d --build"
echo "Then check:"
echo "  docker compose logs --tail=50 notifications"
