#!/bin/sh
set -eu

if [ -n "${DOWNLOAD_LIBRARY_DIR:-}" ]; then
    upload_temp_dir="${DOWNLOAD_LIBRARY_DIR}/.upload-tmp"
    mkdir -p "$upload_temp_dir"
    chmod 700 "$upload_temp_dir"
    # A container restart means no upload can still be active. Remove only
    # recognized incomplete staging files left by an interrupted request.
    find "$upload_temp_dir" \
        -mindepth 1 \
        -maxdepth 1 \
        -type f \
        \( -name '*.upload*' -o -name '.nvgs-web-upload-*.part' \) \
        -delete
fi

python manage.py migrate --noinput

exec gunicorn nvgs_server.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS:-3}" \
    --timeout "${GUNICORN_TIMEOUT:-3600}" \
    --access-logfile - \
    --error-logfile - \
    --capture-output
