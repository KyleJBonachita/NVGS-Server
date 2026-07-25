#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

if [[ ! -f .env ]]; then
    echo "Missing .env. Run scripts/bootstrap-secrets.sh first." >&2
    exit 1
fi

# .env is a root/user-owned deployment file and contains only simple settings.
set -a
source .env
set +a

backup_dir="$project_dir/backups"
mkdir -p "$backup_dir"
chmod 700 "$backup_dir"

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
final_file="$backup_dir/nvgs_ticketing_${timestamp}.dump"
temporary_file="$(mktemp "$backup_dir/.nvgs_backup_XXXXXX")"

cleanup() {
    if [[ -f "$temporary_file" ]]; then
        rm -f -- "$temporary_file"
    fi
}
trap cleanup EXIT

docker compose exec -T db pg_dump \
    --username "${POSTGRES_USER:-nvgs_app}" \
    --dbname "${POSTGRES_DB:-nvgs_ticketing}" \
    --format custom > "$temporary_file"

chmod 600 "$temporary_file"
mv -- "$temporary_file" "$final_file"
trap - EXIT

echo "Backup created: $final_file"
echo "Copy it to a second approved encrypted device and test restores regularly."

