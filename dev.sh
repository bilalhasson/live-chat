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

# Load local secrets/config (e.g. ANTHROPIC_API_KEY to enable the AI Suggest button).
# .env is gitignored — safe place for a key during local dev.
if [ -f "$DIR/.env" ]; then
  set -a; . "$DIR/.env"; set +a
  echo "Loaded .env"
fi

# Warn if something else already holds port 8000 (a common cross-project clash).
# runserver still binds 127.0.0.1:8000, but 'localhost' can resolve to IPv6 (::1)
# and hit the other listener instead — which looks like a blank/404 root page.
if lsof -nP -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "⚠️  Port 8000 is already in use by another process:"
  lsof -nP -iTCP:8000 -sTCP:LISTEN | grep -v '^COMMAND' | awk '{print "     " $1 " (pid " $2 ")"}' | sort -u
  echo "   'localhost:8000' may hit that instead of live-chat. Use http://127.0.0.1:8000/,"
  echo "   or free the port (e.g. stop the other container) and re-run."
  echo ""
fi

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
