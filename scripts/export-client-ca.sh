#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

if [[ "${EUID}" -eq 0 ]]; then
    echo "Run this from your normal Ubuntu account, without sudo." >&2
    exit 1
fi

if ! docker compose ps --status running --services | grep -qx "caddy"; then
    echo "Caddy is not running. Open NVGS Server Control first." >&2
    exit 1
fi

temporary_file="$(mktemp "$project_dir/.nvgs_ca_XXXXXX")"
cleanup() {
    rm -f -- "$temporary_file"
}
trap cleanup EXIT

docker compose cp \
    caddy:/data/caddy/pki/authorities/local/root.crt \
    "$temporary_file"
test -s "$temporary_file"
chmod 0644 "$temporary_file"
mv -- "$temporary_file" "$project_dir/nvgs-local-ca.crt"
trap - EXIT

echo "Public client certificate exported:"
echo "  $project_dir/nvgs-local-ca.crt"
echo
echo "SHA-256 fingerprint:"
sha256sum "$project_dir/nvgs-local-ca.crt"
echo
echo "The public certificate may be copied to approved client laptops."
echo "Never copy files from secrets/ or Caddy's private-key folders."
