#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

if [[ "${EUID}" -ne 0 ]]; then
    user_id="$(id -u)"
    runtime_dir="${XDG_RUNTIME_DIR:-/run/user/${user_id}}"
    controller_lock="$runtime_dir/nvgs-download-server-control.lock"

    exec 8> "$controller_lock"
    if ! flock -n 8; then
        echo "DownloadServer Control is already open." >&2
        read -r -p "Press Enter to close..." _
        exit 1
    fi

    if ! "$project_dir/scripts/ensure-lan-ready.sh"; then
        echo "DownloadServer stopped because the LAN could not be recovered." >&2
        read -r -p "Press Enter to close..." _
        exit 1
    fi

    set +e
    sudo -- "$0"
    controller_status="$?"
    set -e
    exit "$controller_status"
fi

if [[ ! -f compose.yaml || ! -d download-server ]]; then
    echo "DownloadServer cannot start because its project files are missing." >&2
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

download_port="$(read_env_value "DOWNLOAD_SERVER_PORT")"
download_port="${download_port:-8080}"
stable_server_name="$(read_env_value "DOWNLOAD_SERVER_NAME")"
stable_server_name="${stable_server_name:-download-system.local}"
preferred_interface="$(read_env_value "NVGS_ACTIVE_LAN_INTERFACE")"
preferred_interface="${preferred_interface:-$(read_env_value "NVGS_LAN_INTERFACE")}"
if [[ ! "$download_port" =~ ^[0-9]+$ ]] \
    || (( download_port < 1 || download_port > 65535 )); then
    echo "DOWNLOAD_SERVER_PORT must be a number from 1 to 65535." >&2
    read -r -p "Press Enter to close..." _
    exit 1
fi

session_started=false
mdns_published=false

stop_session() {
    trap - EXIT HUP INT TERM
    if [[ "$session_started" == "true" ]]; then
        echo
        echo "Stopping DownloadServer..."
        docker compose --profile downloads stop download-server || true
        if [[ "$mdns_published" == "true" ]]; then
            "$project_dir/scripts/refresh-download-mdns.sh" --remove || true
        fi
        echo "DownloadServer is stopped. Shared files were not changed."
    fi
}
trap stop_session EXIT HUP INT TERM

echo "Starting DownloadServer..."
download_ip=""
if [[ -n "$preferred_interface" \
    && "$preferred_interface" =~ ^[A-Za-z0-9_.:-]+$ \
    && -d "/sys/class/net/$preferred_interface" ]]; then
    download_ip="$(
        ip -4 -o address show dev "$preferred_interface" scope global 2>/dev/null \
            | awk 'NR == 1 {split($4, address, "/"); print address[1]}'
    )"
fi
if [[ -z "$download_ip" ]]; then
    download_ip="$(
        if command -v nmcli >/dev/null 2>&1; then
            while IFS=: read -r candidate candidate_type _state; do
                if [[ "$candidate_type" != "ethernet" ]]; then
                    continue
                fi
                candidate_ip="$(
                    ip -4 -o address show dev "$candidate" scope global 2>/dev/null \
                        | awk 'NR == 1 {split($4, address, "/"); print address[1]}'
                )"
                if [[ -n "$candidate_ip" ]]; then
                    printf '%s\n' "$candidate_ip"
                    break
                fi
            done < <(nmcli -t -f DEVICE,TYPE,STATE device status 2>/dev/null || true)
        else
            ip -4 -o address show scope global 2>/dev/null \
                | awk '$2 ~ /^(en|eth)/ {
                    split($4, address, "/"); print address[1]; exit
                }'
        fi
    )"
fi
if [[ -z "$download_ip" ]]; then
    download_ip="$(
        ip -4 route get 1.1.1.1 2>/dev/null \
            | awk 'NR == 1 {
                for (i=1; i<=NF; i++) if ($i=="src") {print $(i+1); exit}
            }'
    )"
fi
if [[ -z "$download_ip" ]]; then
    download_ip="$(
        ip -4 -o address show scope global 2>/dev/null \
            | awk '$2 !~ /^(lo|docker|br-|veth|virbr|podman|tailscale)/ {
                split($4, address, "/"); print address[1]; exit
            }'
    )"
fi
if [[ -z "$download_ip" ]]; then
    echo "DownloadServer has no usable LAN IPv4 address." >&2
    exit 1
fi
"$project_dir/scripts/refresh-download-mdns.sh" --publish "$download_ip"
mdns_published=true
session_started=true
docker compose --profile downloads up -d --build download-server

running_services="$(
    docker compose --profile downloads ps --status running --services
)"
if ! grep -Fxq "download-server" <<< "$running_services"; then
    echo "DownloadServer did not start correctly. Current container status:" >&2
    docker compose --profile downloads ps -a >&2 || true
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
docker compose --profile downloads ps download-server
echo
echo "DOWNLOADSERVER IS RUNNING"
echo "- This computer: http://localhost:${download_port}/"
if [[ -n "$stable_server_name" ]]; then
    echo "- Stable name: http://${stable_server_name}:${download_port}/"
fi
if [[ "${#lan_addresses[@]}" -eq 0 ]]; then
    echo "- No active Ethernet or Wi-Fi IPv4 address was detected."
else
    for lan_address in "${lan_addresses[@]}"; do
        interface_name="${lan_address%% *}"
        address="${lan_address#* }"
        echo "- ${interface_name}: http://${address}:${download_port}/"
    done
fi
echo "- Shared folder: ${project_dir}/download-server/downloads"
echo "- Files added to that folder appear after the page is refreshed."
echo "- Keep this terminal open while downloads are needed."
echo
echo "Press Enter to stop DownloadServer cleanly."
echo "Closing this window also stops it."
echo

systemd-inhibit \
    --what=sleep:idle:handle-lid-switch \
    --who="DownloadServer Control" \
    --why="Local download server session is running" \
    --mode=block \
    bash -c 'read -r _'
