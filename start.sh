#!/usr/bin/env bash
# Railway start command. Runs migrations + collectstatic, then boots the ASGI
# server (Daphne). NOTE: Daphne, not gunicorn — this is the ASGI/Channels app.
set -e

python manage.py migrate --noinput
python manage.py collectstatic --noinput

exec daphne -b 0.0.0.0 -p "${PORT:-8000}" config.asgi:application
