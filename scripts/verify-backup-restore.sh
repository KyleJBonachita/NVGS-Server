#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

if [[ "${EUID}" -eq 0 ]]; then
    echo "Run this from your normal Ubuntu account, without sudo." >&2
    exit 1
fi

backup_file="${1:-}"
if [[ -z "$backup_file" ]]; then
    backup_file="$(
        find "$project_dir/backups" -maxdepth 1 -type f -name '*.dump' \
            -printf '%T@ %p\n' 2>/dev/null \
            | sort -nr \
            | head -n 1 \
            | cut -d' ' -f2-
    )"
fi
if [[ -z "$backup_file" || ! -s "$backup_file" ]]; then
    echo "No non-empty backup was found. Run ./scripts/backup.sh first." >&2
    exit 1
fi
backup_file="$(realpath "$backup_file")"

container_name="nvgs-restore-check-$(date -u +%Y%m%d%H%M%S)-$$"
database_name="nvgs_restore_check"
report_dir="$project_dir/backups/restore-verifications"
report_file="$report_dir/$(date -u +%Y%m%dT%H%M%SZ).txt"

cleanup() {
    docker rm --force "$container_name" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "Starting an isolated PostgreSQL container with no published network port..."
docker run --detach \
    --name "$container_name" \
    --env POSTGRES_HOST_AUTH_METHOD=trust \
    --env "POSTGRES_DB=$database_name" \
    postgres:17.10-bookworm >/dev/null

ready=false
for _attempt in $(seq 1 30); do
    if docker exec "$container_name" \
        pg_isready --username postgres --dbname "$database_name" >/dev/null 2>&1; then
        ready=true
        break
    fi
    sleep 2
done
if [[ "$ready" != "true" ]]; then
    echo "The isolated restore database did not become ready." >&2
    exit 1
fi

docker cp "$backup_file" "$container_name:/tmp/restore.dump"
docker exec "$container_name" \
    pg_restore \
    --username postgres \
    --dbname "$database_name" \
    --no-owner \
    --no-privileges \
    /tmp/restore.dump

user_count="$(
    docker exec "$container_name" \
        psql --username postgres --dbname "$database_name" --tuples-only --no-align \
        --command 'SELECT COUNT(*) FROM accounts_user;'
)"
ticket_count="$(
    docker exec "$container_name" \
        psql --username postgres --dbname "$database_name" --tuples-only --no-align \
        --command 'SELECT COUNT(*) FROM tickets_ticket;'
)"
comment_count="$(
    docker exec "$container_name" \
        psql --username postgres --dbname "$database_name" --tuples-only --no-align \
        --command 'SELECT COUNT(*) FROM tickets_ticketcomment;'
)"

mkdir -p "$report_dir"
chmod 700 "$report_dir"
{
    echo "NVGS isolated restore verification"
    echo "UTC time: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "Backup: $backup_file"
    echo "Users restored: $user_count"
    echo "Tickets restored: $ticket_count"
    echo "Comments restored: $comment_count"
    echo "Result: PASS"
} > "$report_file"
chmod 600 "$report_file"

echo
echo "Restore verification PASSED."
echo "  Users: $user_count"
echo "  Tickets: $ticket_count"
echo "  Comments: $comment_count"
echo "  Report: $report_file"
echo
echo "The live NVGS database was not changed."
