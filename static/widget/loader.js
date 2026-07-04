/*
 * Live-chat widget loader — Phase 2.
 *
 * A framework-agnostic, single-script-tag widget:
 *   - renders inside a Shadow DOM so the host page's CSS can't touch it (and
 *     vice-versa),
 *   - is configured entirely via data-* attributes on its own <script> tag,
 *   - connects to /ws/visitor/ for its Site and remembers the visitor across
 *     reloads via a localStorage token.
 *
 * Config (all optional except data-site-key):
 *   data-site-key   which Site (tenant) this widget belongs to
 *   data-color      accent colour (default #2563eb)
 *   data-position   "bottom-right" (default) or "bottom-left"
 *   data-greeting   opening message shown at the top of the panel
 */
(function () {
  "use strict";

  var script =
    document.currentScript ||
    (function () {
      var s = document.getElementsByTagName("script");
      return s[s.length - 1];
    })();

  function attr(name, fallback) {
    var v = script && script.getAttribute(name);
    return v != null && v !== "" ? v : fallback;
  }

  var siteKey = attr("data-site-key", window.LIVECHAT_SITE_KEY || "");
  var color = attr("data-color", "#2563eb");
  var position = attr("data-position", "bottom-right") === "bottom-left" ? "left" : "right";
  var greeting = attr("data-greeting", "Hi! How can we help?");

  var backendOrigin;
  try {
    backendOrigin = new URL(script.src).origin;
  } catch (e) {
    backendOrigin = window.location.origin;
  }

  var tokenKey = "livechat_token_" + siteKey;
  function getToken() { try { return localStorage.getItem(tokenKey) || ""; } catch (e) { return ""; } }
  function setToken(t) { try { localStorage.setItem(tokenKey, t); } catch (e) {} }

  function wsUrl() {
    return backendOrigin.replace(/^http/, "ws") + "/ws/visitor/" +
      "?site=" + encodeURIComponent(siteKey) + "&token=" + encodeURIComponent(getToken());
  }

  // --- Shadow DOM host (isolated from the page's CSS) -------------------
  var host = document.createElement("div");
  host.style.position = "fixed";
  host.style.bottom = "20px";
  host.style[position] = "20px";
  host.style.zIndex = "2147483000";
  document.body.appendChild(host);

  var shadow = host.attachShadow({ mode: "open" });
  shadow.innerHTML = [
    "<style>",
    ".wrap{display:flex;flex-direction:column;align-items:flex-end;font-family:system-ui,-apple-system,sans-serif}",
    ".wrap.left{align-items:flex-start}",
    ".panel{width:320px;height:420px;max-width:80vw;background:#fff;border:1px solid #e5e7eb;",
    "border-radius:12px;box-shadow:0 12px 32px rgba(0,0,0,.18);display:none;flex-direction:column;",
    "overflow:hidden;margin-bottom:12px}",
    ".panel.open{display:flex}",
    ".hdr{padding:14px 16px;color:#fff;font-size:15px;font-weight:600;background:#2563eb}",
    ".log{flex:1;padding:12px;overflow-y:auto;background:#fafafa}",
    ".row{display:flex;border-top:1px solid #e5e7eb}",
    ".inp{flex:1;border:none;padding:13px 14px;font-size:14px;outline:none;font-family:inherit}",
    ".bubble{align-self:flex-end;padding:12px 18px;border-radius:24px;border:none;color:#fff;",
    "font-size:14px;cursor:pointer;box-shadow:0 4px 12px rgba(0,0,0,.2);background:#2563eb}",
    ".wrap.left .bubble{align-self:flex-start}",
    ".msg{max-width:78%;padding:8px 11px;border-radius:12px;margin-bottom:8px;font-size:14px;line-height:1.35;",
    "word-wrap:break-word;white-space:pre-wrap}",
    ".msg.visitor{color:#fff;margin-left:auto;background:#2563eb}",
    ".msg.operator{background:#fff;border:1px solid #e5e7eb;color:#111827}",
    "</style>",
    '<div class="wrap' + (position === "left" ? " left" : "") + '">',
    '  <div class="panel">',
    '    <div class="hdr"></div>',
    '    <div class="log"></div>',
    '    <div class="row"><input class="inp" type="text" placeholder="Type a message…" /></div>',
    "  </div>",
    '  <button class="bubble">Chat</button>',
    "</div>",
  ].join("");

  var panel = shadow.querySelector(".panel");
  var hdr = shadow.querySelector(".hdr");
  var log = shadow.querySelector(".log");
  var input = shadow.querySelector(".inp");
  var bubble = shadow.querySelector(".bubble");

  // Apply the configured accent colour (set on elements, never injected into CSS).
  hdr.style.background = color;
  bubble.style.background = color;
  hdr.textContent = "Chat with us";

  var panelOpen = false;
  bubble.addEventListener("click", function () {
    panelOpen = !panelOpen;
    panel.classList.toggle("open", panelOpen);
    if (panelOpen) input.focus();
  });

  // --- WebSocket --------------------------------------------------------
  var socket;
  function connect() {
    if (!siteKey) { hdr.textContent = "Chat unavailable"; return; }
    socket = new WebSocket(wsUrl());
    socket.onopen = function () { hdr.textContent = "Chat with us"; };
    socket.onclose = function () { hdr.textContent = "Reconnecting…"; setTimeout(connect, 1500); };
    socket.onmessage = function (e) {
      var data = JSON.parse(e.data);
      if (data.type === "welcome") {
        setToken(data.token);
      } else if (data.type === "history") {
        renderIntro();
        data.messages.forEach(addMessage);
      } else if (data.type === "message") {
        addMessage(data.message);
      }
    };
  }

  input.addEventListener("keydown", function (e) {
    if (e.key !== "Enter") return;
    var body = input.value.trim();
    if (!body || !socket || socket.readyState !== WebSocket.OPEN) return;
    socket.send(JSON.stringify({ body: body }));
    input.value = "";
  });

  connect();

  // --- helpers ----------------------------------------------------------
  function renderIntro() {
    log.innerHTML = "";
    if (greeting) {
      var intro = mkBubble("operator", greeting);
      log.appendChild(intro);
    }
  }

  function addMessage(m) {
    log.appendChild(mkBubble(m.role, m.body));
    log.scrollTop = log.scrollHeight;
  }

  function mkBubble(role, text) {
    var div = document.createElement("div");
    div.className = "msg " + (role === "visitor" ? "visitor" : "operator");
    div.textContent = text;
    if (role === "visitor") div.style.background = color;
    return div;
  }
})();
