#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

if [[ "${EUID}" -eq 0 ]]; then
    echo "Run this from your normal Ubuntu account, without sudo." >&2
    exit 1
fi
if [[ "$#" -lt 1 || "$#" -gt 2 ]]; then
    echo "Usage: ./scripts/copy-backup-encrypted.sh APPROVED_DEVICE_FOLDER [BACKUP]" >&2
    exit 1
fi
if ! command -v gpg >/dev/null 2>&1; then
    echo "GnuPG is required. Install the Ubuntu package named gnupg." >&2
    exit 1
fi

destination="$(realpath "$1")"
if [[ ! -d "$destination" || ! -w "$destination" ]]; then
    echo "The destination must be an existing writable folder." >&2
    exit 1
fi
case "$destination/" in
    "$project_dir/"*)
        echo "The second backup must not be stored inside the NVGS project." >&2
        exit 1
        ;;
esac

backup_file="${2:-}"
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

output_file="$destination/$(basename "$backup_file").gpg"
if [[ -e "$output_file" ]]; then
    echo "Encrypted copy already exists: $output_file" >&2
    exit 1
fi

temporary_file="$(mktemp --tmpdir="$destination" .nvgs_encrypted_XXXXXX)"
cleanup() {
    rm -f -- "$temporary_file"
}
trap cleanup EXIT
rm -f -- "$temporary_file"

echo "Encrypting $(basename "$backup_file") for the approved second device."
echo "Create a strong backup passphrase and store it in the approved password manager."
gpg --symmetric --cipher-algo AES256 --output "$temporary_file" "$backup_file"
test -s "$temporary_file"
chmod 600 "$temporary_file"
mv -- "$temporary_file" "$output_file"
trap - EXIT

echo
echo "Encrypted second copy created:"
echo "  $output_file"
echo "Storage device: $(findmnt -no SOURCE -T "$destination" 2>/dev/null || echo unknown)"
echo
echo "Keep the passphrase separate from both the server and this backup device."
