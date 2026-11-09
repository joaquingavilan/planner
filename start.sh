#!/bin/sh
set -e
python manage.py migrate --noinput
python manage.py seed          # solo si la base está vacía
python manage.py ensure_user   # exige APP_PASSWORD
exec gunicorn config.wsgi --bind 0.0.0.0:${PORT:-8000} --workers 2 --access-logfile -
