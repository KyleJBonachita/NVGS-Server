#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "Usage: sudo ./scripts/install-ca-ubuntu-client.sh CERTIFICATE --install"
}

if [[ "${EUID}" -ne 0 ]]; then
    usage >&2
    exit 1
fi
if [[ "$#" -ne 2 || "$2" != "--install" ]]; then
    echo "Certificate trust changes the security of this laptop." >&2
    echo "Use --install only on an approved client after checking the fingerprint." >&2
    usage >&2
    exit 1
fi

certificate="$(realpath "$1")"
if [[ ! -s "$certificate" ]]; then
    echo "Certificate file was not found or is empty: $certificate" >&2
    exit 1
fi

echo "Installing this certificate fingerprint:"
openssl x509 -in "$certificate" -noout -fingerprint -sha256
install -m 0644 \
    "$certificate" \
    /usr/local/share/ca-certificates/nvgs-local-ca.crt
update-ca-certificates

echo "NVGS certificate installed. Close and reopen the browser before testing."
