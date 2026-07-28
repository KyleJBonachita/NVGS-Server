#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

if [[ "${EUID}" -eq 0 ]]; then
    echo "Run this helper from your normal Ubuntu account, without sudo." >&2
    exit 1
fi

usage() {
    cat <<'EOF'
NVGS Apps Script notification helper

Commands:
  ./scripts/appscript-notification-setup.sh prepare
  ./scripts/appscript-notification-setup.sh enable APPS_SCRIPT_EXEC_URL
  ./scripts/appscript-notification-setup.sh status
  ./scripts/appscript-notification-setup.sh disable
EOF
}

read_env_value() {
    local key="$1"
    sed -n "s/^[[:space:]]*${key}[[:space:]]*=[[:space:]]*//p" .env \
        | tail -n 1 \
        | tr -d '\r'
}

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

require_local_configuration() {
    if [[ ! -f .env || ! -s secrets/appscript_notification_secret ]]; then
        ./scripts/bootstrap-secrets.sh
    fi
    if [[ ! -f .env || ! -s secrets/appscript_notification_secret ]]; then
        echo "The notification bridge configuration could not be prepared." >&2
        exit 1
    fi
}

restart_if_running() {
    local running_services host_mode
    running_services="$(docker compose ps --status running --services 2>/dev/null || true)"
    host_mode="$(read_env_value "NVGS_HOST_MODE")"
    if grep -qx "app" <<< "$running_services"; then
        echo "Applying notification configuration to the running server..."
        docker compose up -d --build
    elif [[ "${host_mode:-always_on}" == "on_demand" ]]; then
        echo "Configuration saved. Reopen NVGS Server Control to apply it."
    else
        docker compose up -d --build
    fi
}

show_prepare() {
    echo
    echo "Create a NEW standalone Apps Script project named:"
    echo "  NVGS Notification Bridge"
    echo
    echo "Copy these tracked files into that project:"
    echo "  appscript-notification-bridge/Code.gs"
    echo "  appscript-notification-bridge/appsscript.json"
    echo
    echo "Add these Script Properties:"
    echo "  NVGS_NOTIFICATION_INBOX_EMAIL = the original POWER_AUTOMATE_INBOX_EMAIL"
    echo "  NVGS_NOTIFICATION_SENDER_ALIAS = the original FLOW_SENDER_ALIAS"
    echo
    echo "NVGS_NOTIFICATION_SECRET is the private line below:"
    echo "----- COPY SECRET; NEVER SEND OR SCREENSHOT IT -----"
    tr -d '\r\n' < secrets/appscript_notification_secret
    echo
    echo "----- END SECRET -----"
    echo
    echo "Then follow docs/APPSCRIPT_NOTIFICATION_BRIDGE.md."
}

enable_bridge() {
    local deployment_url="$1"
    if [[ ! "$deployment_url" =~ ^https://script[.]google[.]com/[A-Za-z0-9._/-]+/exec$ ]]; then
        echo "Use the deployed https://script.google.com/.../exec URL." >&2
        echo "Do not use a /dev test URL." >&2
        exit 1
    fi
    set_env_value "TICKET_NOTIFICATION_DELIVERY_MODE" "appscript"
    set_env_value "TICKET_NOTIFICATION_APPSCRIPT_URL" "$deployment_url"
    set_env_value "TICKET_NOTIFICATION_EMAIL_TARGET_NAME" "OpsGroupChat"
    chmod 0600 .env
    chmod 0644 secrets/appscript_notification_secret
    restart_if_running
    echo
    echo "Apps Script ticket notifications are enabled."
    echo "Create one clearly marked pilot ticket and check Power Automate/Teams."
}

show_status() {
    local mode deployment_url secret_status
    mode="$(read_env_value "TICKET_NOTIFICATION_DELIVERY_MODE")"
    deployment_url="$(read_env_value "TICKET_NOTIFICATION_APPSCRIPT_URL")"
    secret_status="missing"
    if [[ -s secrets/appscript_notification_secret ]]; then
        secret_status="ready"
    fi
    echo "Ticket notification mode: ${mode:-disabled}"
    echo "Apps Script deployment: ${deployment_url:-not configured}"
    echo "Notification secret file: $secret_status"
}

disable_bridge() {
    set_env_value "TICKET_NOTIFICATION_DELIVERY_MODE" "disabled"
    chmod 0600 .env
    restart_if_running
    echo "Ticket notifications are disabled. Tickets still save normally."
}

command_name="${1:-}"
case "$command_name" in
    prepare)
        require_local_configuration
        show_prepare
        ;;
    enable)
        require_local_configuration
        if [[ -z "${2:-}" || -n "${3:-}" ]]; then
            usage >&2
            exit 1
        fi
        enable_bridge "$2"
        ;;
    status)
        require_local_configuration
        show_status
        ;;
    disable)
        require_local_configuration
        disable_bridge
        ;;
    *)
        usage >&2
        exit 1
        ;;
esac
