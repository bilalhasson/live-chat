# Live Chat — embeddable widget

An embeddable live-chat widget (Intercom / Crisp / Tawk.to style): a site owner drops
one `<script>` tag on any website and visitors chat in real time with an operator.

Built on **Django + Channels** (WebSockets) with a **Redis** channel layer and
**PostgreSQL**, deployed on **Railway**. See `../plans/websocket.md` for the full
phased plan.

> **Status: Phase 0 — walking skeleton (LIVE).** Proves ASGI + WebSockets + Redis
> fan-out + `<script>`-tag embedding + deploy all work end to end. No real chat
> features yet.
>
> **Live:** <https://web-production-dc5e0.up.railway.app/>

## Architecture note (why this isn't a normal Django deploy)

This is an **ASGI** app, not WSGI:

- Served by **Daphne** (`daphne config.asgi:application`), not gunicorn.
- `config/asgi.py` is a **`ProtocolTypeRouter`**: HTTP → Django, `websocket` → Channels.
- **Redis is required** — it's the channel layer that fans WebSocket messages out
  across processes and browser tabs.

## Local development

Requires Python 3.12 and Docker (for Redis).

```bash
# One-time: create the venv + install deps
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt

# Every session: boots Redis (docker compose), migrates, ensures a dev
# superuser (admin / password), and runs the ASGI dev server.
./dev.sh
```

Then open <http://localhost:8000/>. Ctrl+C stops the server and tears down Redis.

Then open <http://localhost:8000/> — the demo "host page" with the widget. Open it in
**two tabs**, send a message in one, and watch it appear in the other (Redis fan-out).

Env vars are read from the process environment; see `.env.example`. Locally the
defaults (SQLite + `redis://127.0.0.1:6379/0`) work with no `.env` file.

## Deploying to Railway

1. `railway login` and create a project.
2. Add two services to the project: **PostgreSQL** and **Redis** (they auto-inject
   `DATABASE_URL` and `REDIS_URL`).
3. Deploy this directory as the app service (`railway up`, or connect the repo).
4. Set service variables:
   - `SECRET_KEY` — a real random value
   - `DEBUG=false`
   - `ALLOWED_HOSTS` — your Railway domain, e.g. `live-chat-xxxx.up.railway.app`
   - `CSRF_TRUSTED_ORIGINS` — `https://live-chat-xxxx.up.railway.app`
5. The start command comes from the `Procfile` (`./start.sh`), which runs
   `migrate` + `collectstatic` then boots Daphne on `$PORT`.

### Definition of done (Phase 0)

- [x] Live Railway URL responds (`/healthz` → `ok`).
- [x] Demo page serves the widget; WebSocket round-trip works (verified live).
- [x] Message from one client reaches a second client (Redis fan-out — verified live
      with a two-client `wss://` test).
- [ ] Cross-origin embed — open `examples/host.html` (points at the live backend) and
      confirm the widget connects. *(Manual browser check.)*
