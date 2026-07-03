#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$DIR/.venv"

if [ ! -d "$VENV" ]; then
  echo "Error: venv not found at $VENV"
  echo "Run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi

cd "$DIR"
PYTHON="$VENV/bin/python"

cleanup() {
  echo ""
  echo "Shutting down..."
  kill $PID_SERVER 2>/dev/null
  docker compose -f "$DIR/docker-compose.yml" down
  wait 2>/dev/null
  echo "Done."
}
trap cleanup EXIT

echo "Starting Redis (channel layer)..."
docker compose -f "$DIR/docker-compose.yml" up -d

echo "Waiting for Redis..."
for i in $(seq 1 30); do
  if docker compose -f "$DIR/docker-compose.yml" exec -T redis redis-cli ping >/dev/null 2>&1; then
    echo "Redis ready."
    break
  fi
  sleep 1
done

echo "Applying migrations..."
"$PYTHON" manage.py migrate

echo "Seeding operator + demo site..."
"$PYTHON" manage.py seed_demo

echo "Starting Django ASGI dev server..."
"$PYTHON" manage.py runserver &
PID_SERVER=$!

echo ""
echo "Running. Open http://localhost:8000/  —  Ctrl+C to stop."
wait
