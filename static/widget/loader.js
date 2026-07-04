/*
 * Live-chat widget loader — Phase 3.
 *
 * Phase 2 gave us Shadow-DOM isolation + data-* theming. Phase 3 adds presence and
 * typing: the header shows whether an operator is online/away, shows "typing…" when
 * the operator is typing, and the widget sends its own (debounced) typing signal.
 * Message-type strings mirror chat/events.py.
 *
 * Config (data-* on the <script> tag): data-site-key (required), data-color,
 * data-position (bottom-right|bottom-left), data-greeting.
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
    ".hdr{padding:12px 16px;color:#fff;background:#2563eb}",
    ".htitle{font-size:15px;font-weight:600}",
    ".hsub{font-size:12px;opacity:.85;margin-top:2px;min-height:14px}",
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
    '    <div class="hdr"><div class="htitle">Chat with us</div><div class="hsub"></div></div>',
    '    <div class="log"></div>',
    '    <div class="row"><input class="inp" type="text" placeholder="Type a message…" /></div>',
    "  </div>",
    '  <button class="bubble">Chat</button>',
    "</div>",
  ].join("");

  var panel = shadow.querySelector(".panel");
  var hdr = shadow.querySelector(".hdr");
  var hsub = shadow.querySelector(".hsub");
  var log = shadow.querySelector(".log");
  var input = shadow.querySelector(".inp");
  var bubble = shadow.querySelector(".bubble");

  hdr.style.background = color;
  bubble.style.background = color;

  var panelOpen = false;
  bubble.addEventListener("click", function () {
    panelOpen = !panelOpen;
    panel.classList.toggle("open", panelOpen);
    if (panelOpen) input.focus();
  });

  // --- status line: presence, overridden transiently by "typing…" --------
  var operatorOnline = null;      // null = unknown yet
  function presenceText() {
    if (operatorOnline === true) return "We're online";
    if (operatorOnline === false) return "We're away — leave a message";
    return "";
  }
  function refreshStatus() { hsub.textContent = presenceText(); }

  var typingTimer;
  function showOperatorTyping() {
    hsub.textContent = "typing…";
    clearTimeout(typingTimer);
    typingTimer = setTimeout(refreshStatus, 4000);
  }
  function clearOperatorTyping() { clearTimeout(typingTimer); refreshStatus(); }

  // --- WebSocket --------------------------------------------------------
  var socket;
  function connect() {
    if (!siteKey) { hsub.textContent = "unavailable"; return; }
    socket = new WebSocket(wsUrl());
    socket.onopen = function () { refreshStatus(); };
    socket.onclose = function () { hsub.textContent = "reconnecting…"; setTimeout(connect, 1500); };
    socket.onmessage = function (e) {
      var data = JSON.parse(e.data);
      switch (data.type) {
        case "welcome":
          setToken(data.token);
          break;
        case "history":
          renderIntro();
          data.messages.forEach(addMessage);
          break;
        case "message":
          clearOperatorTyping();
          addMessage(data.message);
          break;
        case "presence":
          if (data.scope === "operator") { operatorOnline = data.online; refreshStatus(); }
          break;
        case "typing":
          if (data.role === "operator") { data.typing ? showOperatorTyping() : clearOperatorTyping(); }
          break;
      }
    };
  }

  // --- outgoing typing (debounced) --------------------------------------
  var typingSent = false, typingIdle;
  function sendTyping(on) {
    if (!socket || socket.readyState !== WebSocket.OPEN || on === typingSent) return;
    typingSent = on;
    socket.send(JSON.stringify({ action: "typing", typing: on }));
  }
  input.addEventListener("input", function () {
    sendTyping(true);
    clearTimeout(typingIdle);
    typingIdle = setTimeout(function () { sendTyping(false); }, 2500);
  });
  input.addEventListener("keydown", function (e) {
    if (e.key !== "Enter") return;
    var body = input.value.trim();
    if (!body || !socket || socket.readyState !== WebSocket.OPEN) return;
    socket.send(JSON.stringify({ body: body }));
    input.value = "";
    clearTimeout(typingIdle);
    sendTyping(false);
  });

  connect();

  // --- helpers ----------------------------------------------------------
  function renderIntro() {
    log.innerHTML = "";
    if (greeting) log.appendChild(mkBubble("operator", greeting));
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
