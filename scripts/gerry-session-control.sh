#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

if [[ "${EUID}" -ne 0 ]]; then
    user_id="$(id -u)"
    runtime_dir="${XDG_RUNTIME_DIR:-/run/user/${user_id}}"
    controller_lock="$runtime_dir/nvgs-gerry-server-control.lock"

    exec 8> "$controller_lock"
    if ! flock -n 8; then
        echo "Gery Chatbot Server Control is already open." >&2
        read -r -p "Press Enter to close..." _
        exit 1
    fi

    if ! "$project_dir/scripts/ensure-lan-ready.sh"; then
        echo "Gery stopped because the LAN could not be recovered." >&2
        read -r -p "Press Enter to close..." _
        exit 1
    fi

    set +e
    sudo -- "$0"
    controller_status="$?"
    set -e
    exit "$controller_status"
fi

if [[ ! -f compose.yaml || ! -d Chatbot_Gery_the_Robot_Assistant ]]; then
    echo "Gery cannot start because its project files are missing." >&2
    read -r -p "Press Enter to close..." _
    exit 1
fi
if [[ ! -s secrets/gery_admin_token ]]; then
    echo "Gery's administrator secret is missing." >&2
    echo "Run ./scripts/bootstrap-secrets.sh once, then try again." >&2
    read -r -p "Press Enter to close..." _
    exit 1
fi

read_env_value() {
    local key="$1"
    if [[ ! -f .env ]]; then
        return 0
    fi
    sed -n "s/^[[:space:]]*${key}[[:space:]]*=[[:space:]]*//p" .env \
        | tail -n 1 \
        | tr -d '\r'
}

gerry_port="$(read_env_value "GERY_SERVER_PORT")"
gerry_port="${gerry_port:-3000}"
if [[ ! "$gerry_port" =~ ^[0-9]+$ ]] \
    || (( gerry_port < 1 || gerry_port > 65535 )); then
    echo "GERY_SERVER_PORT must be a number from 1 to 65535." >&2
    read -r -p "Press Enter to close..." _
    exit 1
fi

session_started=false
stop_session() {
    trap - EXIT HUP INT TERM
    if [[ "$session_started" == "true" ]]; then
        echo
        echo "Stopping Gery Chatbot Server..."
        docker compose --profile chatbot stop gerry || true
        echo "Gery is stopped. Uploaded knowledge and its index were not changed."
    fi
}
trap stop_session EXIT HUP INT TERM

echo "Starting Gery Chatbot Server..."
session_started=true
docker compose --profile chatbot up -d --build gerry

running_services="$(docker compose --profile chatbot ps --status running --services)"
if ! grep -Fxq "gerry" <<< "$running_services"; then
    echo "Gery did not start correctly. Current container status:" >&2
    docker compose --profile chatbot ps -a >&2 || true
    exit 1
fi

mapfile -t lan_addresses < <(
    ip -4 -o address show scope global 2>/dev/null \
        | awk '
            $2 !~ /^(docker|br-|veth|virbr|podman|tailscale)/ {
                split($4, address, "/");
                print $2 " " address[1]
            }
        '
)

echo
docker compose --profile chatbot ps gerry
echo
echo "GERY CHATBOT SERVER IS RUNNING"
echo "- This computer: http://localhost:${gerry_port}/"
if [[ "${#lan_addresses[@]}" -eq 0 ]]; then
    echo "- No active Ethernet or Wi-Fi IPv4 address was detected."
else
    for lan_address in "${lan_addresses[@]}"; do
        interface_name="${lan_address%% *}"
        address="${lan_address#* }"
        echo "- ${interface_name}: http://${address}:${gerry_port}/"
    done
fi
echo "- Knowledge manager on Ubuntu: http://localhost:${gerry_port}/admin/"
echo "- Secure remote manager (while NVGS runs): https://<NVGS-address>/gerry/admin/"
echo "- The floating widget is now available to NVGS and DownloadServer."
echo "- Uploaded knowledge: ${project_dir}/Chatbot_Gery_the_Robot_Assistant/data/uploads"
echo "- Keep this terminal open while Gery is needed."
echo
echo "Press Enter to stop Gery cleanly."
echo "Closing this window also stops it."
echo

systemd-inhibit \
    --what=sleep:idle:handle-lid-switch \
    --who="Gery Chatbot Server Control" \
    --why="Local chatbot server session is running" \
    --mode=block \
    bash -c 'read -r _'
