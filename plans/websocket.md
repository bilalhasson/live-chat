# PLAN — Embeddable Live Chat Widget

> Intended home: `plans/websocket.md`. This file is the plan-mode working copy; on
> approval I'll copy it to `plans/websocket.md` in the project (I can't create that
> file while in plan mode).

## Context

A portfolio piece whose **deliberate learning goal is real-time / WebSockets** — the
author (full-stack Django/Celery/React/AWS engineer) has shipped small solo projects
but never built WebSockets. We're building an embeddable live-chat widget in the
Intercom / Crisp / Tawk.to mould: a site owner drops one `<script>` tag on any site,
visitors chat in real time with an operator who reads/replies from a dashboard.

Because it's a portfolio piece the rules are: **it must end up live on a real URL**,
scope stays ruthlessly small per phase, one new concept at a time, and "boring and
finished" beats "clever and abandoned." Deploy first, features second.

## Decisions locked with the user

| Decision | Choice | Why |
|---|---|---|
| **Real-time transport** | **Django Channels + Redis channel layer** | The idiomatic Django way to learn WS; Redis layer is what fans messages out across processes. `AsyncWebsocketConsumer` + `channel_layers`. |
| **Tenancy** | **Multi-tenant** | Site/Workspace model + public widget key, conversations isolated per site. Data model designed in from Phase 1; self-serve UI deferred to a later phase. |
| **Operator view** | **Minimal operator dashboard** | Authenticated Django page: conversation list + live thread + reply box. Operator side is *also* a WS client → real-time on both ends. Deliberately bare visually. |
| **Visitor identity** | **Anonymous + optional pre-chat form** | Auto anonymous ID in localStorage (persists across reloads); optional name/email prompt added in a later phase. |
| **AI replies** | **Later phase, suggest-a-reply** | Human-only early; one dedicated phase adds an Anthropic-powered "suggest a reply" button, human in the loop. Kept out of early phases. |
| **Style isolation** | **Shadow DOM** | CSS encapsulation from host page while the widget still sizes/positions/animates freely (iframes fight sizing + the bubble→panel animation). |
| **Scope stance** | **Portfolio-first, but built to actually run** | Real auth, real persistence, sensible data model — without gold-plating for scale. |

## Stack

- **Backend:** Django + Django Channels, `channels_redis` channel layer.
- **Data:** PostgreSQL (app data), Redis (channel layer / pub-sub fan-out).
- **Widget:** plain vanilla JS. **Must not assume React on the host site.** Shadow DOM.
- **Deploy:** Railway Hobby (~$5/mo) — Postgres service + Redis service + the app.

---

## ⚠️ The Railway / ASGI deployment wrinkle (read before Phase 0)

This is **not** a normal WSGI Django deploy. What changes vs. a standard `gunicorn`
Django app on Railway:

1. **ASGI server, not WSGI.** Start command runs Daphne (Channels' reference server):
   `daphne config.asgi:application -b 0.0.0.0 -p $PORT`
   (Uvicorn is a fine alternative.) There is **no `gunicorn`**.
2. **`asgi.py` becomes a `ProtocolTypeRouter`**, not a bare `get_asgi_application()` —
   it routes `http` to Django and `websocket` to the Channels URL router.
3. **Redis is required, not optional.** Add a Railway Redis service and set
   `CHANNEL_LAYERS` to `channels_redis.core.RedisChannelLayer` reading `REDIS_URL`.
   Without it, WS messages can't fan out across workers/tabs.
4. **Cross-origin WebSocket origin check is a real gotcha.** Channels'
   `AllowedHostsOriginValidator` will **reject** WS connections from arbitrary host
   pages — which is exactly what an embeddable widget does. Phase 0 uses a permissive
   validator; Phase 2 replaces it with a custom validator that checks the connection
   origin against the **registered Site's allowed domain(s)**.
5. **`ALLOWED_HOSTS` + `CSRF_TRUSTED_ORIGINS`** must include the Railway domain.
6. **Static/CORS for the loader script.** `loader.js` is fetched cross-origin from
   other people's sites → serve with permissive CORS + correct content-type
   (WhiteNoise for statics, or a dedicated view).
7. **One process serves both HTTP and WS** in v1 (consumers run in the ASGI process).
   **No Celery needed for v1.** Scale to multiple Daphne instances later — Redis
   already makes that correct.

---

## Phase 0 — Walking skeleton (DEPLOY FIRST)

**Goal:** the smallest end-to-end proof that ASGI + WebSockets + Redis channel layer +
`<script>`-tag embedding + Railway deploy all work together, live. No features.

**In scope:**
- Django project with Channels installed; `asgi.py` as `ProtocolTypeRouter`.
- One `EchoConsumer` that joins a Redis-backed group and echoes/broadcasts a message
  (broadcasting proves the Redis channel layer, not just a single socket).
- One static `loader.js` that, when included via `<script>`, injects a placeholder
  button/div, opens a WS to the server, sends `ping`, and renders the `pong`.
- A separate test host HTML page (ideally a *different origin*) carrying the script tag.
- Deployed to Railway: app + Postgres + Redis services, Daphne start command,
  env vars wired.

**Definition of done:**
- A live Railway URL exists.
- Opening the test page shows the placeholder widget and a visible WS round-trip (echo).
- Redis channel layer confirmed: a broadcast from one tab appears in a second tab.
- Deploy is reproducible (documented start command + env vars).

**Deliberately excluded:** persistence, real chat UI, auth, multi-tenancy, styling,
Shadow DOM, config attributes.

---

## Phase 1 — Core real-time chat

**Goal:** real visitor ↔ operator messaging over WebSockets, persisted to Postgres,
appearing live on both sides.

**In scope:**
- **Models (multi-tenant-ready from day one, but seeded single Site):** `Site`
  (with `public_key`, allowed domain), `Visitor`, `Conversation` (FK Site + Visitor),
  `Message` (FK Conversation, sender role, body, timestamp). One `Site` is seeded; the
  **self-serve tenant UI is deferred** so multi-tenancy doesn't leak into this phase.
- **Visitor consumer:** joins its conversation's group, persists inbound messages,
  broadcasts to the group; loads history on connect.
- **Operator dashboard:** authenticated Django page — conversation list (left), live
  thread (right), reply box. It is **itself a WS client** subscribed to its Site's
  conversations. Bare styling.
- Messages persist; history loads on (re)connect on both sides.

**Definition of done:**
- Send from the test widget → message appears live in the operator dashboard.
- Operator replies → reply appears live in the widget.
- Reload either side → full history persists.
- Everything works on the deployed Railway URL, not just locally.

**Deliberately excluded:** Shadow DOM, config data attributes, typing indicators,
pre-chat form, self-serve multi-site, notifications, canned responses, AI.

---

## Phase 2 — Real embeddable widget

**Goal:** a production-quality, framework-agnostic single script tag — style-isolated
and configurable — that works dropped onto any third-party site.

**In scope:**
- Rewrite `loader.js` into a proper vanilla-JS widget: floating bubble → expanding
  chat panel, message list, input, connection-status indicator.
- **Shadow DOM** style isolation (immune to host-page CSS; host CSS unaffected).
- **Config via data attributes:** `data-site-key`, `data-color`, `data-position`,
  `data-greeting`.
- **Anonymous visitor ID** in localStorage → conversation continuity across reloads.
- **Cross-origin correctness:** custom Channels origin validator checks WS origin
  against the Site's registered domain; loader served with correct CORS.

**Definition of done:**
- Drop **one** script tag with data attributes onto an unrelated HTML page on a
  *different origin*; the widget renders correctly regardless of the host's CSS.
- Configured colour / position / greeting are respected.
- The same visitor is recognised across reloads (persistent anonymous ID).
- Live chat with the operator works end-to-end on the deployed URL.

**Deliberately excluded:** everything in Phase 3+.

---

## Phase 3+ — Feature menu (one concept per phase, ordered but flexible)

Ship these one at a time; stop whenever it's a strong portfolio piece. Each phase gets
its own goal / DoD / exclusions when we start it.

1. **Presence & polish** — typing indicators, online/away/offline states,
   delivery/read state, operator browser + sound notifications, offline → capture
   message. *(Low effort, high perceived polish; strong next step.)*
2. **Pre-chat form + visitor metadata + email transcript** — optional name/email,
   page URL / referrer / geo, and email-transcript continuity when the visitor leaves.
3. **Self-serve multi-tenancy** — operator signup, create a Site, copy your snippet,
   manage widget settings. *This is what makes the multi-tenant architecture visible
   as a real product.*
4. **Canned responses** — saved replies for the operator.
5. **AI-assisted suggested replies (Anthropic API)** — a "suggest a reply" button in
   the operator dashboard; human stays in the loop. The headline portfolio flourish.

---

## Later / out of scope (parking lot for temptations)

Autonomous AI auto-reply · no-code chatbot flows · multi-channel inbox (WhatsApp / FB /
IG / SMS / email) · knowledge base / in-widget article search · co-browsing · audio /
video calls · live translation · analytics/reporting dashboards · conversation tagging /
assignment / teams / private notes · proactive triggered campaigns · CRM integrations ·
public webhooks / REST API · SLAs / workflow-automation engine · Celery-backed async
jobs · horizontal scaling beyond one Daphne process.

---

## Verification (how we prove each phase, end-to-end)

- **Local first, then deployed** — every phase's DoD must be demonstrated on the live
  Railway URL, not just `localhost`, because the ASGI/Redis/origin wrinkles only bite
  in deploy.
- **Two-window test** — visitor widget in one browser/window, operator dashboard in
  another; confirm live bidirectional flow and that history survives reload.
- **Redis fan-out test (Phase 0)** — broadcast reaches a second tab, proving the
  channel layer isn't just an in-memory single-socket illusion.
- **Cross-origin embed test (Phase 2)** — host the test page on a genuinely different
  origin (e.g. a static host / GitHub Pages) and confirm the widget connects, i.e. the
  origin validator and CORS are correct.
- **Persistence check** — inspect Postgres (`Conversation` / `Message`) to confirm
  messages are stored, not just relayed.
- **Deploy reproducibility** — start command, env vars (`DATABASE_URL`, `REDIS_URL`,
  `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `SECRET_KEY`) documented so the app can be
  rebuilt from scratch.

---

# Phase 3 — Presence & Polish (detailed build plan)

## Context
Phases 0–2 are shipped and live on `live-chat.bilalhasson.com` (deploy skeleton →
real-time chat → embeddable Shadow-DOM widget). Phase 3 adds the "it feels alive"
layer: typing indicators, online/away presence (both directions), and operator
notifications. The explicit ask is that it stays **easy to maintain and cleanly
separated into relevant files** — so the growing WebSocket protocol and the new
ephemeral-presence concern get their own modules rather than being smeared across
the consumers, and the operator dashboard's JS moves out of the HTML template.

**Scope (confirmed):** typing indicators (both directions), operator online/away
shown to visitors, visitor-online shown to operators, and browser + sound
notifications with unread badges. **Read/delivery receipts are deferred.**

## Core design principle: ephemeral signals are NOT persisted
Messages are durable (already in Postgres via `services.py`). Typing and presence
are **transient** — they flow over the Redis channel layer only and are never
written to the DB. This separation is the backbone of the phase: `services.py`
(DB) stays untouched by presence; a new `presence.py` owns the transient state.

## File separation (the maintainability core)

### Backend — new modules
- **`chat/events.py` (NEW)** — the single source of truth for the WS protocol.
  Today the type strings (`"welcome"`, `"message"`, `"chat.message"`, …) are
  scattered as literals across `consumers.py`, `loader.js`, and `operator.html`.
  Centralise them here as constants + small payload-builder functions:
  - Channel-layer event types: `CHAT_MESSAGE="chat.message"`,
    `CONVERSATION_UPDATE="conversation.update"`, `TYPING="typing.event"`,
    `PRESENCE="presence.event"`.
  - Outbound client types: `"welcome"`, `"history"`, `"message"`,
    `"conversations"`, `"conversation_update"`, `"typing"`, `"presence"`.
  - Builders, e.g. `typing_payload(conversation_id, role, is_typing)`,
    `presence_payload(...)`. Consumers import these instead of hand-writing dicts.
- **`chat/presence.py` (NEW)** — all ephemeral presence, isolated behind an async
  API backed by a Redis **set** (uses `redis.asyncio.from_url(settings.REDIS_URL)`;
  `redis` is already a pinned dep). Keys per site:
  `presence:site:<id>:ops` (operator channel names) and
  `presence:site:<id>:online_convs` (conversation ids with a live visitor).
  Functions: `operator_join/leave(site_id, channel) -> (count, transitioned)`,
  `is_operator_online(site_id)`, `visitor_join/leave(site_id, conv_id)`,
  `online_conversation_ids(site_id)`. **Known limitation (documented in-module):**
  an unclean crash leaves a stale set member; acceptable for v1, with a TTL/heartbeat
  upgrade noted as future work.
- **`chat/groups.py` (CHANGED)** — add `site_visitors_group(site_id)` so operator
  presence can fan out to every visitor of a site.

### Backend — thin consumer changes (`chat/consumers.py`)
Consumers stay transport-only; they delegate to `events`, `presence`, `groups`,
`services`. Additions:
- **VisitorConsumer:** also join `site_visitors_group`; on connect call
  `presence.visitor_join` + broadcast a visitor-online `presence.event` to the site
  ops group, and send this visitor the current operator availability
  (`presence.is_operator_online`); on disconnect mirror it. `receive` dispatches
  `{action:"typing", typing}` → broadcast `typing.event(role=visitor)` to the conv
  group (plain `{body}` still = a message, unchanged). New handlers `typing_event`
  (forward only the *operator's* typing — skip own role) and `presence_event`
  (operator availability).
- **OperatorConsumer:** on connect `presence.operator_join` per owned site and, on a
  0→1 transition, broadcast operator-online to `site_visitors_group`; merge
  `presence.online_conversation_ids` into the `conversations` payload so the sidebar
  shows live dots. `receive` gains `{action:"typing", conversation_id, typing}` →
  broadcast `typing.event(role=operator)` (authorized via `services.conv_site_id`).
  New handlers `typing_event` (forward only the *visitor's* typing) and
  `presence_event` (update the sidebar dot). On disconnect, `operator_leave` and
  broadcast away on a 1→0 transition.
- `services.py` stays DB-only; the presence merge happens in the consumer, keeping
  the DB and ephemeral layers cleanly apart.

### Frontend — extract and extend
- **`static/operator/operator.js` (NEW)** — move the ~84 lines of inline JS out of
  `operator.html` into a real static file, then extend it: debounced typing send on
  the reply box; render "visitor is typing…"; per-conversation online dots; browser
  **Notification** (permission-gated) + a short **Web Audio beep** (no binary asset)
  + unread badges that clear on open/focus.
- **`templates/operator.html` (CHANGED)** — `{% load static %}`, drop the inline
  `<script>`, load `{% static 'operator/operator.js' %}`; add DOM hooks (typing line,
  sidebar dots, unread badge spans). CSS stays inline for now (optional future
  extract to `static/operator/operator.css`).
- **`static/widget/loader.js` (CHANGED)** — debounced typing send on input; show
  "typing…" and an online/away status in the header; handle the new `"typing"` and
  `"presence"` client message types. Served as today via the `/widget.js` view.

## Protocol additions (defined once in `events.py`)
- Inbound: visitor `{action:"typing", typing:bool}`; operator
  `{action:"typing", conversation_id, typing:bool}`.
- Channel-layer: `typing.event` and `presence.event` (→ `typing_event` /
  `presence_event` handler methods).
- Outbound client: `{"type":"typing", conversation_id, role, typing}` and
  `{"type":"presence", scope:"operator"|"visitor", conversation_id?, online}`.
- Debounce: send `typing:true` on input, auto-send `typing:false` after ~2.5s idle
  and on message send; receiver also self-expires the indicator on a local timer.
- Self-echo filtered in the handlers (a sender never shows its own typing).

## Definition of done
- Typing shows live in both directions, debounced, and auto-clears.
- Widget header reflects operator online vs away; operator sidebar shows a live dot
  for conversations with a connected visitor (and back-fills on connect via the
  merged conversations list).
- New visitor message in a not-currently-viewed/unfocused conversation → browser
  notification + sound + incremented unread badge; badge clears on open/focus.
- Presence and typing are verifiably **not** written to Postgres.
- `phase1_e2e` and `phase2_origin` still pass; new presence/typing tests pass.
- Works end-to-end on `live-chat.bilalhasson.com` after deploy.

## Deliberately excluded
Read/delivery ("seen"/"delivered") receipts; persistent unread counts (reset on
reload in v1); presence heartbeats / TTL crash-recovery (documented limitation);
offline→email capture (belongs with the Phase 4 pre-chat/transcript work); AI.

## Verification
- **Automated (extend the scratch e2e harness):**
  - *Typing:* operator opens a conv; visitor sends `{action:"typing",typing:true}` →
    operator receives `typing` (role=visitor); operator→visitor mirror; confirm no
    self-echo.
  - *Presence:* with a visitor connected, an operator connect → visitor receives
    `presence{operator, online:true}`, disconnect → `online:false`; a visitor
    connect → operator receives `presence{visitor, conversation_id, online:true}`
    and the `conversations` list carries the online flag.
  - *No persistence:* assert `Message` row count is unchanged after typing/presence
    traffic.
  - *Regression:* re-run `phase1_e2e` and `phase2_origin`.
- **Manual (browser), local via `./dev.sh` then live:** two windows (widget +
  `/operator/`) — see typing dots, online/away header, sidebar presence dot,
  notification + sound + unread badge; confirm operator JS now loads from
  `/static/operator/operator.js`.
- **Deploy:** commit + push (auto-deploys); re-run the live visitor WS check and
  confirm typing/presence frames arrive over `wss://live-chat.bilalhasson.com`.

---

# Phase 4 — Self-serve multi-tenancy (detailed build plan)

## Context
The multi-tenant architecture already exists (`Site.owner` / `public_key` /
`allowed_domain`) but is invisible: one seeded operator, one hardcoded site. This
phase exposes it as a real product — **open public signup**, create/manage your own
sites, copy an embed snippet, and control the widget's appearance from a dashboard.
It reframes the whole piece from "my chat demo" into "a SaaS you can sign up for,"
and it's the natural home for the widget theming we currently hardcode in the snippet.

**Confirmed:** open public signup (username + password, email optional — collect the
minimum); widget appearance is **dashboard-controlled** (the widget fetches its config
by site-key at load; the snippet is just one line).

## Model change
- Add to `Site`: `color` (default `#2563eb`), `position` (default `bottom-right`),
  `greeting` (default `Hi! How can we help?`). Migration. (`name`, `public_key`,
  `allowed_domain` already exist.)

## Dashboard-controlled theming
- **New public endpoint** `GET /widget/<site_key>/config.json` → `{name, color,
  position, greeting}` with `Access-Control-Allow-Origin: *` + short cache; 404 for an
  unknown key. (Lives in `views.py` next to `widget_js`, same CORS pattern.)
- **`static/widget/loader.js` (CHANGED):** on load, fetch config by site-key from the
  backend origin, merge with any `data-*` overrides (attributes win, for
  back-compat), *then* build the Shadow-DOM widget and connect. Fall back to
  `data-*`/defaults if the fetch fails.
- The embed snippet collapses to one clean line:
  `<script src="https://live-chat.bilalhasson.com/widget.js" data-site-key="KEY"></script>`.

## Auth + dashboard (open signup)
- **Signup:** `SignupForm` (subclass `UserCreationForm`, optional email). View creates
  the user, `auth.login`s them, redirects to the sites list. `LOGIN_REDIRECT_URL`
  changes from `/operator/` to `/sites/`. (Login/logout already exist.)
- **Site management** — all `login_required` and ownership-scoped via
  `get_object_or_404(Site, pk=…, owner=request.user)` (no IDOR):
  - `/sites/` — list the user's sites + create (via `SiteForm`).
  - `/sites/<id>/` — settings form (`name`, `allowed_domain`, `color`, `position`,
    `greeting`) + the copy-paste snippet + a link to the inbox.
  - `/sites/<id>/delete/` — POST-only delete.
- **Inbox** — the existing operator dashboard already aggregates all the user's sites
  via `services.sites_for_user`; keep it. Add the site name to
  `serializers.serialize_conversation` so a multi-site inbox labels which site each
  conversation belongs to.

## File separation (maintainability)
- **`chat/forms.py` (NEW)** — `SignupForm`, `SiteForm`.
- **`chat/dashboard.py` (NEW)** — authenticated views: `signup`, `site_list`,
  `site_detail`, `site_delete`, and the `inbox` view (moved here from `views.py` for
  cohesion — the realtime consumers are untouched).
- **`chat/views.py` (CHANGED)** — public views only: `demo`, `healthz`, `widget_js`,
  and the new `widget_config`.
- **`templates/dashboard/` (NEW)** — `base.html` (shared nav: Sites / Inbox / Log
  out), `sites.html`, `site_detail.html`, `signup.html`. `login.html` stays;
  `operator.html` remains the inbox template.
- **`config/urls.py` (CHANGED)** — add the signup / sites / config routes.
- **`config/settings.py` (CHANGED)** — `LOGIN_REDIRECT_URL = "/sites/"`.
- **`chat/serializers.py` (CHANGED)** — include site name in the conversation summary.
- **`templates/demo.html` (CHANGED)** — snippet reduced to just `data-site-key`
  (theme now server-driven).
- `seed_demo` unchanged — still provisions the public Demo Site (now with theme
  defaults) used by `/`.

## Definition of done
- A brand-new visitor can: **sign up → create a site → copy the snippet → paste it on
  a separate page → chat**, with the operator replying from the inbox.
- Editing a site's settings in the dashboard restyles the widget via the config
  endpoint — no snippet edit required.
- Ownership enforced: a user cannot view/edit/delete another user's site (404), and
  the inbox shows only their own sites' conversations.
- `phase1_e2e`, `phase2_origin`, `phase3_e2e` still pass; new tests for signup, site
  CRUD ownership, and the config endpoint pass.
- Works end-to-end on `live-chat.bilalhasson.com`.

## Deliberately excluded
Multiple operators / teams per site; roles & permissions; billing; email verification
and password reset (Django has built-ins to add later); per-site analytics;
conversation export/deletion. Parked in "Later / out of scope".

## Verification
- **Automated (Django test client + extend the e2e harness):**
  - signup creates a user, logs in, and redirects to `/sites/`.
  - create a site → owned by the user with a `public_key`; edit persists;
    `config.json` reflects the new theme.
  - ownership: a second user gets 404 on the first user's `/sites/<id>/` and delete.
  - `widget_config` returns the right JSON + CORS header, 404 for a bad key.
  - regression: re-run `phase1_e2e`, `phase2_origin`, `phase3_e2e`.
- **Manual (browser), local via `./dev.sh` then live:** the full self-serve flow —
  sign up, create a site, copy the snippet into `examples/host.html`, chat + reply,
  then change the theme in the dashboard and confirm the widget restyles.
- **Deploy:** commit + push (auto-deploys); sign up a real account on
  `live-chat.bilalhasson.com`, create a site, embed it, and chat.

---

# Phase 5 — AI-assisted suggested replies (detailed build plan)

## Context
The headline finale: a "✨ Suggest" button in the operator inbox that drafts a reply
to the visitor using the Anthropic API, **streaming the draft token-by-token into the
reply box** where the operator edits it and sends it themselves. Human stays in the
loop — the AI never sends a message on its own. It lands hard now because it sits
inside a real multi-tenant product, and it pairs the two headline technologies of the
project: WebSockets (the draft streams over the existing operator socket) and the
Anthropic streaming API.

**Confirmed:** model is **Haiku 4.5** (`claude-haiku-4-5`) — fast and cheap, ideal for
a real-time suggest button — but read from an env var (`ANTHROPIC_MODEL`, default
`claude-haiku-4-5`) so it can be swapped to Sonnet 5 / Opus 4.8 with no code change.

## Design principle: human-in-the-loop, feature-flagged, isolated
- The suggestion only ever populates the operator's **editable** reply box. Sending
  stays the existing manual action. **No auto-reply.**
- The feature is **gated on `ANTHROPIC_API_KEY`**: present → the Suggest button shows;
  absent → the button is hidden and the feature is completely inert (no errors). So
  the app runs fine locally and in prod without a key.
- All Anthropic logic lives in one new module (`chat/ai.py`); the consumer stays thin.

## Per-site AI configuration (owner-tunable)
Each site owner tunes their own assistant from the site settings page. Add three
fields to `Site` (migration):
- `ai_enabled` (bool, default `True`) — per-site on/off, independent of the global key.
- `ai_tone` (text, blank) — voice/style instruction, e.g. "Warm and casual, use the
  visitor's first name."
- `ai_context` (text, blank) — what the business does + key facts/policies. The
  highest-impact field: grounds drafts in the real business (a lightweight stand-in
  for full RAG, which stays out of scope).

These feed the system prompt in `ai.py`. Reply-language and signature are deliberately
**not** separate fields — they can be expressed inside `ai_tone`/`ai_context`; language
can graduate to its own field later if needed. The model stays a global env var
(`ANTHROPIC_MODEL`), not per-site.

Two-level gate: a suggestion runs only if the **global key is present** AND the
conversation's site has `ai_enabled=True`. The Suggest button is shown when the key is
present (`ai_enabled` flag in the `conversations` payload) and enabled per-conversation
from the site's flag (`serialize_conversation` adds `"ai": conv.site.ai_enabled`, a
pure field read). `_suggest` re-checks the site flag server-side as defense.

## New module — `chat/ai.py` (NEW)
Encapsulates everything Anthropic. Uses the **async** SDK (`AsyncAnthropic`) since the
consumers are async, and **streams** (per the Claude API guidance).
- `suggestions_enabled() -> bool` — `bool(os.environ.get("ANTHROPIC_API_KEY"))`.
- `async def stream_suggestion(site_name, tone, context, history)` — an async generator
  yielding text deltas. Builds a system prompt from the site's config ("You are a
  support agent for {site_name}. {context}. Tone: {tone}. Draft a concise reply to the
  visitor's latest message based on the conversation. Output only the reply text.") and
  maps `history` to messages (visitor → `user`, operator → `assistant`), then
  `async with client.messages.stream(model=MODEL,
  max_tokens=300, system=…, messages=…) as stream: async for text in stream.text_stream:
  yield text`. No thinking config (keep it fast); `MODEL = os.environ.get(
  "ANTHROPIC_MODEL", "claude-haiku-4-5")`. Errors propagate to the caller.

## Protocol additions — `chat/events.py` (CHANGED)
- Inbound action: `A_SUGGEST = "suggest"` (`{action: "suggest", conversation_id}`).
- Outbound client types + builders: `suggestion_start`, `suggestion_delta`
  (`{conversation_id, text}`), `suggestion_end`, `suggestion_error` (`{message}`).

## Consumer — `chat/consumers.py` OperatorConsumer (CHANGED, stays thin)
- On connect, include `ai_enabled: ai.suggestions_enabled()` in the `conversations`
  payload so the client knows whether to show the button.
- `receive`: dispatch `A_SUGGEST` → `_suggest(conversation_id)`.
- `_suggest`: authorize via `services.conv_site_id` (ownership); a single-flight guard
  (`self._suggesting`) so a socket can't run two at once; if
  `not ai.suggestions_enabled()` → `suggestion_error`. Fetch the site's AI config +
  history — one small new helper `services.ai_config_for_conversation(id)` →
  `(site_name, tone, context, ai_enabled)`, plus `services.load_history`. If
  `not ai_enabled` → `suggestion_error("AI is off for this site")`. Otherwise send
  `suggestion_start`, then `async for delta in ai.stream_suggestion(name, tone,
  context, history)` → `suggestion_delta`; finish with `suggestion_end`. Wrap in
  `try/except` → `suggestion_error(str-safe message)`; clear the guard in `finally`.
  (`serialize_conversation` also gains the pure `"ai": conv.site.ai_enabled` field.)

## Dashboard settings — `chat/forms.py` + `templates/dashboard/site_detail.html` (CHANGED)
- `SiteForm` gains `ai_enabled`, `ai_tone`, `ai_context` so the owner edits them on the
  site settings page (with help text; `ai_context`/`ai_tone` as textareas). No new view
  logic — reuses the existing `site_detail` save path.

## Frontend — `static/operator/operator.js` + `templates/operator.html` (CHANGED)
- `operator.html`: add a "✨ Suggest" button in the composer and a small inline
  status/error line; minimal CSS. Button hidden by default.
- `operator.js`:
  - Reveal the button only when the global `ai_enabled` flag (from `conversations`) is
    true; enable it per-open-conversation when that conversation's `ai` flag is true
    (disable with a tooltip when the site has AI off).
  - Click (requires an open conversation) → send `{action:"suggest", conversation_id}`;
    disable the button, show "drafting…".
  - `suggestion_start` → clear the reply input. `suggestion_delta` → append `text` to
    the input value (operator watches it fill). `suggestion_end` → re-enable the button,
    focus the input so the operator can edit and press Enter to send (existing flow).
    `suggestion_error` → re-enable + show the inline message.

## Dependencies & config
- `requirements.txt`: add `anthropic` (pin the version pip installs).
- No Django settings change — `ai.py` reads `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL`
  from the environment. Locally, export the key to test; on Railway, set it as a
  service variable (like `OPERATOR_PASSWORD`). `seed_demo` unchanged.

## Definition of done
- With `ANTHROPIC_API_KEY` set: open a conversation → click **✨ Suggest** → a drafted
  reply streams token-by-token into the reply box → operator edits and sends it
  normally. The AI never sends a message itself.
- Without the key: the button is hidden and nothing errors.
- Ownership enforced: a suggestion can't be requested for another operator's
  conversation; a socket can't run two suggestions at once.
- Model swappable via `ANTHROPIC_MODEL` (default `claude-haiku-4-5`).
- `phase1_e2e` / `phase2_origin` / `phase3_e2e` / `phase4_http` still pass; new
  (mocked) AI tests pass.
- Works live on `live-chat.bilalhasson.com`.

## Deliberately excluded
Autonomous auto-reply (AI never sends on its own); RAG / knowledge-base grounding;
per-site AI on/off toggle and model picker in the dashboard; usage metering / billing;
canned responses. Parked in "Later / out of scope".

## Verification
- **Automated (no real API call):** monkeypatch `chat.ai.stream_suggestion` with a fake
  async generator and `chat.ai.suggestions_enabled`; drive the operator socket:
  `{action:"suggest"}` → assert `suggestion_start` → `suggestion_delta`(s) →
  `suggestion_end` in order; assert a suggestion for a non-owned conversation is
  rejected; assert that with `suggestions_enabled()` False the client gets
  `suggestion_error`. Regressions: re-run all four prior e2e suites.
- **Real-API smoke (local, if a key is available):** a small script calling
  `ai.stream_suggestion` on a sample history and printing the streamed text — confirms
  the live integration and model string (costs a few cents).
- **Deploy:** set `ANTHROPIC_API_KEY` on Railway (optional `ANTHROPIC_MODEL`), push,
  then click **✨ Suggest** in the live inbox and watch the draft stream in.

---

# Phase 6 — Canned responses (detailed build plan)

## Context
Saved reply templates the operator inserts instead of retyping common answers
("hours", "reset password", a greeting). Per-site (each owner defines their own,
matching the multi-tenant model). Complements the AI Suggest button: canned responses
are instant, free, and pre-approved; AI drafts are generated and contextual. Both land
in the **editable** reply box — neither auto-sends.

**Confirmed UX:** slash-command — typing `/` at the start of the reply box opens an
inline menu that filters by title as the operator keeps typing; Enter (or click)
inserts the body; the operator then edits/sends as normal.

## Model — `chat/models.py` (CHANGED) + migration
```
class CannedResponse(models.Model):
    site = FK(Site, on_delete=CASCADE, related_name="canned_responses")
    title = CharField(max_length=80)   # the "/shortcut" label
    body = TextField()
    created_at = DateTimeField(auto_now_add=True)
    class Meta: ordering = ["title"]
```
Migration `0004`. Owner-scoped through `site.owner` (no direct owner FK needed).

## Dashboard CRUD (owner manages them per site)
- **`chat/forms.py`** — `CannedResponseForm` (ModelForm: `title`, `body`; body as a
  textarea).
- **`chat/dashboard.py`** — two thin `login_required` views, ownership-scoped:
  - `canned_create(request, pk)` — `get_object_or_404(Site, pk, owner=request.user)`,
    save the form with `site=site`, redirect back to `site_detail`.
  - `canned_delete(request, pk, cid)` — POST-only;
    `get_object_or_404(CannedResponse, pk=cid, site__owner=request.user)`; delete.
  - `site_detail` also passes `site.canned_responses.all()` + a blank
    `CannedResponseForm` to the template (GET display).
- **`config/urls.py`** — `sites/<int:pk>/canned/` and
  `sites/<int:pk>/canned/<int:cid>/delete/`.
- **`templates/dashboard/site_detail.html`** — a "Canned responses" card: list of
  existing (title + a small delete form each) and an add form posting to
  `canned_create`.

## Delivery to the inbox — over the existing WS, fetched fresh on open
Canned responses are per-site; the inbox is multi-site, so they're delivered for the
**conversation the operator opens** (always current from the DB — reflects dashboard
edits on the next open). No new realtime concept; it rides the existing open flow.
- **`chat/services.py`** — `canned_for_site(site_id)` → `[{id, title, body}]` (async).
- **`chat/events.py`** — `C_CANNED = "canned"` + `client_canned(conversation_id,
  responses)`.
- **`chat/consumers.py`** — `OperatorConsumer._open` already resolves the site via
  `services.conv_site_id`; capture that `site_id` and, right after sending history,
  send `client_canned(conversation_id, await services.canned_for_site(site_id))`.
  Stays thin.

## Frontend — `static/operator/operator.js` + `templates/operator.html` (CHANGED)
- `operator.html`: a positioned `#canned-menu` popover above the composer + minimal CSS
  (list items, highlighted selection). No new button — the trigger is `/`.
- `operator.js`:
  - Store the current conversation's list from the `canned` message; reset on `open`.
  - On reply-box `input`: if the value starts with `/`, filter titles by the text after
    the slash (case-insensitive) and show `#canned-menu` (all items for a bare `/`);
    otherwise hide it. Track a selected index.
  - Keyboard (in the existing reply `keydown`, checked **before** the send branch):
    when the menu is open — ArrowUp/Down move the selection, Enter/Tab **inserts** the
    selected body and closes the menu (does **not** send), Escape closes. When the menu
    is closed, Enter sends as today.
  - Insert = replace the reply value with the response body, hide the menu, keep focus
    so the operator can edit and send. Click on an item does the same.

## Definition of done
- Owner creates/lists/deletes canned responses on a site's settings page; ownership
  enforced (can't touch another owner's site or responses → 404).
- Operator opens a conversation → typing `/` opens a menu of that site's canned
  responses, filters as they type; Enter/click inserts the text into the editable reply
  box (does not send); normal Enter still sends when the menu is closed.
- Empty state: a site with no canned responses shows no menu; sending is unaffected.
- `phase1_e2e` … `phase5_ai` still pass; new canned tests pass.
- Works live on `live-chat.bilalhasson.com`.

## Deliberately excluded
Placeholder variables (e.g. `{{name}}` — no real visitor name until the pre-chat form
phase); account-wide/shared canned across sites; categories/folders; usage analytics;
feeding canned responses into the AI prompt as style examples (nice future synergy).

## Verification
- **Automated:**
  - *CRUD + ownership (Django test client, like `phase4_http`):* create a canned
    response for your own site; it belongs to that site; delete works; a second user
    gets 404 creating/deleting against the first user's site.
  - *Delivery (WS):* operator opens a conversation whose site has a canned response →
    receives a `canned` message listing it. Extend the mocked operator-socket harness.
  - *Regressions:* re-run all five prior e2e suites.
- **Manual (browser), local via `./dev.sh` then live:** add a couple of canned
  responses to the Demo Site; in the inbox open a conversation, type `/`, filter,
  Enter to insert, edit, send.
- **Deploy:** commit + push (auto-deploys); repeat the `/` insert on the live inbox.

---

# Phase 7 — Pre-chat form (detailed build plan)

## Context
Let a site owner optionally require visitors to identify themselves before chatting, so
the operator has a real name/email to reply to (and a foundation for email transcripts
later). Per-site toggle, matching the multi-tenant model. Returning visitors (remembered
by their localStorage token) skip the form.

**Confirmed (my recommendation, in the absence of an answer):** the form collects
**name (optional) + email (required)**; the widget also sends its **host page URL** so
the operator sees where the visitor is chatting from. Both are easy to trim later.

## Model changes — `chat/models.py` (CHANGED) + migration `0005`
- `Site`: `pre_chat_enabled` (bool, default `False`).
- `Visitor`: `name` (CharField, blank) + `email` (EmailField, blank) — the captured
  identity, persisted so a returning token skips the form.
- `Conversation`: `page_url` (CharField/URLField, blank) — the host page the visitor is
  on, updated on connect (latest wins).
- `Site.config()` gains `"pre_chat": self.pre_chat_enabled` (already served by
  `widget_config`, so the widget learns it up front — no new endpoint).

## Protocol — `chat/events.py` (CHANGED)
- `welcome` payload gains `identified` (bool = visitor already has an email).
- Inbound visitor action `A_IDENTIFY = "identify"` (`{name, email}`).
- Outbound: `C_IDENTIFIED` (ack → widget switches to the chat view) and
  `C_IDENTIFY_ERROR` (`{message}`, e.g. bad email).

## VisitorConsumer — `chat/consumers.py` (CHANGED, stays thin)
- `connect`: parse a `page` query-string param and store it on the conversation
  (`services.set_conversation_page`); include `identified` in the `welcome`; track
  `self.identified`.
- `receive`:
  - `{action:"identify", name, email}` → validate email (`django.core.validators`);
    on success `services.set_visitor_identity(...)`, set `self.identified = True`, send
    `identified`, and broadcast a `conversation.update` to the site ops group so the
    operator's sidebar shows the name immediately; on invalid email → `identify_error`.
  - **Server-side gate:** for a plain `{body}` message, if
    `self.site.pre_chat_enabled and not self.identified` → drop it (prevents bypassing
    the client-side form). Typing/other actions unaffected.

## Data layer — `chat/services.py` + `chat/serializers.py` (CHANGED)
- `services.set_visitor_identity(visitor_id, name, email)` and
  `set_conversation_page(conversation_id, url)` (async DB helpers).
- `serialize_conversation` gains `name`, `email`, `page_url` (pure field reads;
  `select_related` already loads visitor). Keeps `visitor` (token) as the fallback label.

## Widget — `static/widget/loader.js` (CHANGED)
- Include `&page=<encodeURIComponent(location.href)>` on the WS URL.
- Config already fetched before build now carries `pre_chat`. Build a **pre-chat view**
  inside the panel (name input, required email input, Start button) shown when
  `pre_chat && !identified`; the message input row stays hidden until identified.
- On `welcome`: set `identified`; decide which view to show. On Start: client-validate
  the email, send `{action:"identify", name, email}`; on `identified` → reveal the chat
  input and focus; on `identify_error` → inline message. Returning identified visitors
  (token in localStorage) skip straight to chat.

## Operator inbox — `static/operator/operator.js` + `templates/operator.html` (CHANGED)
- Sidebar: show the visitor's **name** when present, else "Visitor `<token>`"; email as
  subtext.
- Add a small **thread header** above the message list showing the open conversation's
  name · email · page URL; updates live on `conversation_update` (e.g. when a visitor
  identifies mid-session).

## Dashboard — `chat/forms.py` (CHANGED)
- `SiteForm` gains `pre_chat_enabled` (checkbox, with help text). Renders on the existing
  site settings page — no new view/route.

## Definition of done
- Owner toggles **Pre-chat form** on a site. A first-time visitor then sees a
  name+email form (valid email required) before they can send; on submit the chat opens.
- A returning visitor (same localStorage token) skips the form.
- With pre-chat on, a message from an unidentified visitor is **dropped server-side**
  (no client bypass).
- Operator sees the visitor's name/email and page URL in the inbox, updating live when a
  visitor identifies mid-session.
- Pre-chat off → behaves exactly as today.
- All six prior e2e suites still pass; new pre-chat tests pass.
- Works live on `live-chat.bilalhasson.com`.

## Deliberately excluded
Email transcript delivery (its own phase); referrer / geo / UTM metadata beyond page
URL; per-field custom form config; GDPR consent checkbox; letting the visitor edit their
details later. Parked in "Later / out of scope". (PII note: only name/email are
collected, only when the owner enables it — data minimisation; the email is shown to the
operator, which is its purpose, and isn't logged elsewhere.)

## Verification
- **Automated (extend the mocked WS harness):**
  - *Pre-chat off:* visitor `welcome.identified` handling; messages flow as today.
  - *Pre-chat on:* visitor connects → `welcome.identified == false`; a `{body}` sent
    before identifying is dropped (no `Message` row, operator gets nothing); send
    `{action:"identify", name, email}` → `Visitor` saved, `identified` ack, operator
    receives a `conversation_update` carrying the name; a subsequent `{body}` now flows.
  - *Page URL:* connecting with `?page=…` stores it; it appears in the conversation
    summary.
  - *Ownership / regressions:* re-run all six prior suites.
- **Manual (browser), local via `./dev.sh` then live:** enable pre-chat on the Demo
  Site; open the widget → fill the form → chat; confirm the operator sees name/email/page
  and that a returning visitor skips the form.
- **Deploy:** commit + push (auto-deploys, migration `0005`); repeat live.

---

# Phase 8 — Operator ends a chat (detailed build plan)

## Context
Give the operator a way to close out a conversation: it **ends the visitor's session**
(they see a thank-you screen and must start fresh) and **removes the chat from the
operator's inbox**. The transcript is kept in the DB (marked ended), so the thank-you
screen can grow into feedback/rating requests later. This is a soft "end", not a hard
delete.

**Confirmed:** end & keep (retain the transcript, exclude it from the inbox); the visitor
gets a thank-you screen with a **"Start new chat"** button that begins a brand-new
conversation (the ended one is never re-joined).

## Model — `chat/models.py` (CHANGED) + migration `0006`
- `Conversation`: `ended_at` (DateTimeField, null=True, blank=True). `None` = active.

## Data layer — `chat/services.py` (CHANGED)
- `end_conversation(conversation_id)` — set `ended_at = timezone.now()` (async).
- `conversations_for_sites` — filter `ended_at__isnull=True` (ended chats leave the inbox).
- `get_or_create_conversation` — find the latest **non-ended** conversation, else create
  a new one. So a visitor reconnecting after an end starts fresh instead of re-joining
  the ended thread. (`conv_site_id` unchanged — still authorizes by site.)

## Protocol — `chat/events.py` (CHANGED)
- Inbound operator action `A_END = "end"` (`{conversation_id}`).
- Channel-layer events: `CONVERSATION_ENDED = "conversation.ended"` (to the conv group →
  visitor) and `CONVERSATION_REMOVED = "conversation.removed"` (to the site ops group →
  all operators).
- Outbound client: `C_ENDED = "ended"` (visitor → thank-you) and
  `C_CONVERSATION_REMOVED = "conversation_removed"` (`{conversation_id}` → operators drop
  it). Plus the matching builders.

## Consumers — `chat/consumers.py` (CHANGED, stay thin)
- **OperatorConsumer**
  - `receive`: `A_END` → `_end(conversation_id)`.
  - `_end`: authorize via `services.conv_site_id`; `services.end_conversation(...)`;
    `group_send` `conversation.ended` to the conv group and `conversation.removed` to the
    site ops group; if it was `self.current_conv`, leave that conv group + clear it.
  - handlers: `conversation_removed` → send `client_conversation_removed`; `conversation_ended`
    → no-op (an operator viewing the conv is also in the conv group; the removal is driven
    by the site-ops event, but the handler must exist so the group event doesn't error).
- **VisitorConsumer**
  - handler `conversation_ended` → send `client_ended()` (the thank-you trigger).

## Widget — `static/widget/loader.js` (CHANGED)
- Add an **ended view** (like the pre-chat view): a thank-you message + a **"Start new
  chat"** button; minimal CSS.
- On `ended`: show the ended view, hide the input/pre-chat rows, and stop auto-reconnect
  (guard the `onclose` handler with a `stopped` flag; close the socket).
- **"Start new chat"**: clear the `stopped`/ended state, reset the log, and `connect()`
  again → the server hands back a fresh conversation (the old one is ended). Visitor
  identity persists (so a pre-chat site won't re-ask an already-identified visitor).

## Operator inbox — `static/operator/operator.js` + `templates/operator.html` (CHANGED)
- Add an **"End chat"** button to the thread header (only shown with a conversation open);
  click → `confirm(...)` → send `{action:"end", conversation_id}`.
- On `conversation_removed`: delete it from `convs`; if it's the current conversation,
  reset the pane (clear thread + header, disable the reply box, close any canned menu,
  `currentId = null`); `renderList()`. Minimal CSS for the button.

## Definition of done
- Operator opens a conversation → **End chat** (with confirm) → the chat ends.
- A connected visitor sees a thank-you screen with **Start new chat**; clicking it (or
  reloading) starts a brand-new conversation — the ended one is never re-joined, and a
  message can't be sent into an ended chat.
- The ended conversation disappears from **all** operators' inboxes; if it was open, the
  thread pane resets.
- Transcript is retained in the DB (`ended_at` set) and excluded from the inbox list.
- All seven prior e2e suites still pass; a new end-chat test passes.
- Works live on `live-chat.bilalhasson.com`.

## Deliberately excluded
Feedback/rating capture on the thank-you screen (the retained-transcript design makes
this a clean future add); hard delete; an operator "ended/history" view or reopen (data
is in Django admin for now); auto-timeout ending of idle chats.

## Verification
- **Automated (extend the mocked WS harness):**
  - Two operators + a visitor connected to one conversation. Operator A sends
    `{action:"end"}` → the visitor receives `ended`; **both** operators receive
    `conversation_removed` for that id; `Conversation.ended_at` is set;
    `conversations_for_sites` no longer includes it.
  - *Restart:* a fresh visitor connect with the same token returns a **new**
    conversation id (≠ the ended one).
  - *Ownership:* ending a conversation on another operator's site is a no-op (not ended).
  - *Regressions:* re-run all seven prior suites.
- **Manual (browser), local via `./dev.sh` then live:** two windows (widget + inbox);
  chat, then End chat → visitor sees the thank-you + Start new chat, operator's inbox
  drops it; start new chat → a fresh conversation appears.
- **Deploy:** commit + push (auto-deploys, migration `0006`); repeat live.

---

# Phase 9 — Email transcripts (detailed build plan)

## Context
When an operator ends a chat, email the visitor a copy of the conversation. This closes
the loop on the pre-chat email (Phase 7) and the end-chat flow (Phase 8): the visitor
leaves with a record of the exchange. Per-site opt-in.

**Confirmed:** auto-send when the operator **ends the chat**; recipient is the **visitor
only** (at the email they gave in the pre-chat form); delivered via **Resend**, wired up
as its own Django app.

## Email provider — a new `mailer` Django app (Resend)
Per the ask, the email provider lives in its own app so it's isolated and reusable:
- **New app `mailer`** — added to `INSTALLED_APPS`; a thin wrapper around Resend, with
  **no models** (an integration/service app, so no migrations). Knows nothing about chat.
- Uses the official **`resend`** Python SDK (add to `requirements.txt`), API-key auth.
- `mailer/service.py`:
  - `enabled() -> bool` = `bool(os.environ.get("RESEND_API_KEY"))`.
  - `send_email(to, subject, text) -> bool` — sets `resend.api_key`, calls
    `resend.Emails.send({"from": RESEND_FROM, "to": [to], "subject": …, "text": …})`;
    if not `enabled()` it logs the intended email and returns `False`; wrapped in
    `try/except` so it logs and returns `False` on any error (never raises).
- Env: `RESEND_API_KEY` and `RESEND_FROM` (e.g. `"Live Chat <live-chat@bilalhasson.com>"`).
  No Django `EMAIL_*`/SMTP settings — we call Resend directly. Feature-gated on the key,
  exactly like the AI feature.

## Model — `chat/models.py` (CHANGED) + migration `0007`
- `Site`: `transcript_enabled` (bool, default `False`) — owner opt-in.

## Transcript composition — `chat/transcripts.py` (NEW)
Domain logic stays in `chat`; it depends on `mailer`, not the other way round.
- `send_transcript(conversation_id) -> bool` — **synchronous** (ORM reads + a sync Resend
  call). Load the conversation (`select_related` site + visitor); return `False` early
  unless `site.transcript_enabled` **and** `visitor.email` **and** `mailer.enabled()`.
  Build a plain-text transcript (`[time] Name: body` per message, visitor name vs site
  name), then `mailer.send_email(visitor.email, "Your chat transcript with {site}", body)`.

## Consumer — `chat/consumers.py` OperatorConsumer._end (CHANGED, small)
- After ending + the `conversation.ended` / `conversation.removed` broadcasts (so the
  visitor's thank-you and the inbox update are never delayed by the email call), fire it:
  `await sync_to_async(transcripts.send_transcript)(conversation_id)`, wrapped in a
  `try/except` so a mail failure can't break ending. (Add `from asgiref.sync import
  sync_to_async`.)

## Dashboard — `chat/forms.py` (CHANGED)
- `SiteForm` gains `transcript_enabled` (checkbox; help text: "Email the visitor a
  transcript when a chat ends — needs their email and Resend configured"). Renders on the
  existing site settings page; no new route/view.

## Definition of done
- With a site's **Email transcripts** on, a visitor who gave an email is sent their
  transcript via Resend when the operator ends the chat.
- No email is attempted when transcripts are off, there's no visitor email, or Resend
  isn't configured (`RESEND_API_KEY` unset → logs, no send).
- Ending a chat still succeeds even if the email send fails (non-fatal).
- All eight prior e2e suites still pass; a new transcript test passes.
- Works live on `live-chat.bilalhasson.com` once `RESEND_API_KEY` + `RESEND_FROM` are set.

## Deliberately excluded
HTML/branded email templates; operator/owner copy; an on-demand "email transcript"
button; retries / queue (no Celery — a slow send just delays the one `_end` await);
unsubscribe management; sending on visitor-leave (end-chat is the reliable trigger).

## Verification
- **Automated (mock the provider — no real Resend call):**
  - Monkeypatch `mailer.service.send_email` (or `chat.transcripts.mailer.send_email`) with
    a capture stub, and force `mailer.enabled()` True. Site `transcript_enabled=True` +
    a conversation with a visitor email + messages → `transcripts.send_transcript` returns
    `True` and `send_email` was called once with the visitor's address and a body
    containing the message text.
  - Gates: `transcript_enabled=False`, no visitor email, or `enabled()` False → `send_email`
    **not** called.
  - *End flow:* operator `{action:"end"}` on such a conversation → `send_email` invoked
    (extends `phase8_end`'s harness); ending still completes.
  - *Regressions:* re-run all eight prior suites.
- **Manual:** local `./dev.sh` without `RESEND_API_KEY` → ending a transcript-enabled chat
  logs the intended email (disabled); set a real key to actually deliver.
- **Deploy:** set `RESEND_API_KEY` + `RESEND_FROM` on Railway, commit + push (migration
  `0007`), then end a live chat and confirm the visitor receives the email.
