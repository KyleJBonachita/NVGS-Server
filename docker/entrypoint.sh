#!/bin/sh
set -eu

if [ -n "${DOWNLOAD_LIBRARY_DIR:-}" ]; then
    mkdir -p "${DOWNLOAD_LIBRARY_DIR}/.upload-tmp"
    chmod 700 "${DOWNLOAD_LIBRARY_DIR}/.upload-tmp"
fi

python manage.py migrate --noinput

exec gunicorn nvgs_server.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS:-3}" \
    --access-logfile - \
    --error-logfile - \
    --capture-output
