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
NVGS Apps Script login helper

Commands:
  ./scripts/appscript-login-setup.sh prepare
  ./scripts/appscript-login-setup.sh enable APPS_SCRIPT_EXEC_URL
  ./scripts/appscript-login-setup.sh status
  ./scripts/appscript-login-setup.sh disable

Use "prepare" first. It shows the exact Script Properties for this server.
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
    if [[ ! -f .env || ! -s secrets/appscript_bridge_secret ]]; then
        echo "Creating any missing local configuration and secret files..."
        ./scripts/bootstrap-secrets.sh
    fi

    if [[ ! -f .env || ! -s secrets/appscript_bridge_secret ]]; then
        echo "The bridge configuration could not be prepared." >&2
        exit 1
    fi
}

server_url_host() {
    local address
    address="$(read_env_value "SERVER_ADDRESS")"
    address="${address:-localhost}"

    if [[ ! "$address" =~ ^[A-Za-z0-9._:-]+$ ]]; then
        echo "SERVER_ADDRESS contains unsupported characters: $address" >&2
        exit 1
    fi

    if [[ "$address" == *:* && "$address" != \[*\] ]]; then
        printf '[%s]' "$address"
    else
        printf '%s' "$address"
    fi
}

show_prepare() {
    local url_host callback_url login_url
    url_host="$(server_url_host)"
    callback_url="https://${url_host}/api/auth/appscript/consume/"
    login_url="https://${url_host}/api/auth/appscript/start/"

    echo
    echo "Create a standalone Apps Script project with these two files:"
    echo "  appscript-bridge/Code.gs"
    echo "  appscript-bridge/NVGSLoginBridge.gs"
    echo
    echo "Add these five values under Apps Script Project Settings"
    echo "then Script Properties:"
    echo
    echo "NVGS_BRIDGE_CALLBACK_URL=${callback_url}"
    echo "NVGS_BRIDGE_ISSUER=nvgs-appscript"
    echo "NVGS_BRIDGE_AUDIENCE=nvgs-server"
    echo "NVGS_BRIDGE_ALLOWED_DOMAIN=nvidia.com"
    echo
    echo "NVGS_BRIDGE_SECRET is the single private line printed below:"
    echo "----- COPY SECRET; NEVER SEND OR SCREENSHOT IT -----"
    tr -d '\r\n' < secrets/appscript_bridge_secret
    echo
    echo "----- END SECRET -----"
    echo
    echo "Deploy the Apps Script as a web app:"
    echo "  Execute as: User accessing the web app"
    echo "  Access: NVIDIA domain only"
    echo
    echo "After deployment, copy its URL ending in /exec and run:"
    echo "  ./scripts/appscript-login-setup.sh enable 'PASTE_EXEC_URL_HERE'"
    echo
    echo "The eventual NVGS login address will be:"
    echo "  ${login_url}"
    if [[ "$url_host" == "localhost" ]]; then
        echo
        echo "IMPORTANT: localhost can be tested only in a browser on this Ubuntu laptop."
        echo "Other laptops need the Ubuntu server's approved LAN address first."
    fi
}

restart_if_running() {
    local running_services host_mode
    running_services="$(docker compose ps --status running --services 2>/dev/null || true)"
    host_mode="$(read_env_value "NVGS_HOST_MODE")"

    if grep -qx "app" <<< "$running_services"; then
        echo "Applying the login configuration to the running server..."
        docker compose up -d --build
    elif [[ "${host_mode:-always_on}" == "on_demand" ]]; then
        echo "Configuration saved."
        echo "Open NVGS Server Control to start with the new setting."
    else
        echo "Starting the server with the new login configuration..."
        docker compose up -d --build
    fi
}

enable_bridge() {
    local deployment_url="$1"
    if [[ ! "$deployment_url" =~ ^https://script[.]google[.]com/[A-Za-z0-9._/-]+/exec$ ]]; then
        echo "The deployment URL must start with https://script.google.com/" >&2
        echo "and end with /exec. Do not use the /dev test URL." >&2
        exit 1
    fi

    set_env_value "APPSCRIPT_SSO_ENABLED" "true"
    set_env_value "APPSCRIPT_SSO_URL" "$deployment_url"
    set_env_value "APPSCRIPT_SSO_ISSUER" "nvgs-appscript"
    set_env_value "APPSCRIPT_SSO_AUDIENCE" "nvgs-server"
    set_env_value "APPSCRIPT_SSO_AUTO_CREATE_USERS" "true"
    set_env_value "APPSCRIPT_SSO_SUCCESS_REDIRECT" "/tickets/"
    chmod 600 .env secrets/appscript_bridge_secret

    restart_if_running

    echo
    echo "Apps Script login is enabled."
    echo "Open this address in the Ubuntu browser:"
    echo "  https://$(server_url_host)/api/auth/appscript/start/"
}

show_status() {
    local enabled deployment_url url_host secret_status
    enabled="$(read_env_value "APPSCRIPT_SSO_ENABLED")"
    deployment_url="$(read_env_value "APPSCRIPT_SSO_URL")"
    url_host="$(server_url_host)"
    secret_status="missing"
    if [[ -s secrets/appscript_bridge_secret ]]; then
        secret_status="ready"
    fi

    echo "Apps Script login enabled: ${enabled:-false}"
    echo "Apps Script deployment: ${deployment_url:-not configured}"
    echo "Bridge secret file: ${secret_status}"
    echo "Callback URL: https://${url_host}/api/auth/appscript/consume/"
    echo "Login URL: https://${url_host}/api/auth/appscript/start/"
}

disable_bridge() {
    set_env_value "APPSCRIPT_SSO_ENABLED" "false"
    chmod 600 .env
    restart_if_running
    echo "Apps Script login is disabled. Local account login remains available."
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
