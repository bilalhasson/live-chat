/*
 * Live-chat widget loader — Phase 4.
 *
 * The embed snippet is now just: <script src=".../widget.js" data-site-key="KEY">.
 * Appearance (colour, position, greeting) is set by the site owner in the dashboard
 * and fetched at load time from /widget/<key>/config.json. data-* attributes still
 * work as local overrides, and defaults apply if the fetch fails.
 *
 * Renders inside a Shadow DOM (isolated from host-page CSS). Message-type strings
 * mirror chat/events.py.
 */
(function () {
  "use strict";

  var script =
    document.currentScript ||
    (function () {
      var s = document.getElementsByTagName("script");
      return s[s.length - 1];
    })();

  function override(name) {
    var v = script && script.getAttribute(name);
    return v != null && v !== "" ? v : null;
  }

  var siteKey = override("data-site-key") || window.LIVECHAT_SITE_KEY || "";
  var overrides = {
    color: override("data-color"),
    position: override("data-position"),
    greeting: override("data-greeting"),
  };

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
      "?site=" + encodeURIComponent(siteKey) +
      "&token=" + encodeURIComponent(getToken()) +
      "&page=" + encodeURIComponent(location.href);
  }

  // Resolve config (server + data-* overrides), then build + connect.
  fetchConfig(function (cfg) {
    var color = overrides.color || cfg.color || "#2563eb";
    var pos = (overrides.position || cfg.position) === "bottom-left" ? "left" : "right";
    var greeting = overrides.greeting || cfg.greeting || "Hi! How can we help?";
    start(color, pos, greeting, !!cfg.pre_chat);
  });

  function fetchConfig(cb) {
    if (!siteKey) { cb({}); return; }
    fetch(backendOrigin + "/widget/" + encodeURIComponent(siteKey) + "/config.json")
      .then(function (r) { return r.ok ? r.json() : {}; })
      .then(cb)
      .catch(function () { cb({}); });
  }

  function start(color, position, greeting, preChat) {
    // --- Shadow DOM host (isolated from the page's CSS) ---
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
      ".prechat{display:none;flex-direction:column;gap:8px;padding:12px;border-top:1px solid #e5e7eb;background:#fff}",
      ".prechat.show{display:flex}",
      ".prechat input{border:1px solid #d1d5db;border-radius:6px;padding:9px 10px;font-size:14px;outline:none;font-family:inherit}",
      ".prechat button{border:none;border-radius:6px;padding:10px;color:#fff;font-size:14px;cursor:pointer;background:#2563eb}",
      ".prechat .err{color:#b91c1c;font-size:12px;min-height:14px}",
      ".row.hidden{display:none}",
      ".ended{display:none;flex-direction:column;gap:12px;padding:20px 16px;border-top:1px solid #e5e7eb;background:#fff;text-align:center}",
      ".ended.show{display:flex}",
      ".ended-msg{font-size:14px;color:#374151}",
      ".ended button{border:none;border-radius:6px;padding:10px;color:#fff;font-size:14px;cursor:pointer;background:#2563eb}",
      "</style>",
      '<div class="wrap' + (position === "left" ? " left" : "") + '">',
      '  <div class="panel">',
      '    <div class="hdr"><div class="htitle">Chat with us</div><div class="hsub"></div></div>',
      '    <div class="log"></div>',
      '    <form class="prechat">',
      '      <input class="pc-name" type="text" placeholder="Your name (optional)" />',
      '      <input class="pc-email" type="email" placeholder="Your email" required />',
      '      <div class="err"></div>',
      '      <button class="pc-start" type="submit">Start chat</button>',
      "    </form>",
      '    <div class="row"><input class="inp" type="text" placeholder="Type a message…" /></div>',
      '    <div class="ended">',
      '      <div class="ended-msg">Thanks for chatting with us! 👋</div>',
      '      <button class="ended-new" type="button">Start new chat</button>',
      "    </div>",
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
    var prechat = shadow.querySelector(".prechat");
    var pcName = shadow.querySelector(".pc-name");
    var pcEmail = shadow.querySelector(".pc-email");
    var pcErr = shadow.querySelector(".prechat .err");
    var pcStart = shadow.querySelector(".pc-start");
    var row = shadow.querySelector(".row");
    var endedView = shadow.querySelector(".ended");
    var endedNew = shadow.querySelector(".ended-new");

    hdr.style.background = color;
    bubble.style.background = color;
    pcStart.style.background = color;
    endedNew.style.background = color;
    var stopped = false;  // true once an operator has ended the chat

    // Pre-chat gate: until we hear otherwise, assume unidentified when pre-chat is on.
    var identified = !preChat;
    function updateGate() {
      var needForm = preChat && !identified;
      prechat.classList.toggle("show", needForm);
      row.classList.toggle("hidden", needForm);
    }
    updateGate();

    var panelOpen = false;
    bubble.addEventListener("click", function () {
      panelOpen = !panelOpen;
      panel.classList.toggle("open", panelOpen);
      if (panelOpen) (prechat.classList.contains("show") ? pcEmail : input).focus();
    });

    prechat.addEventListener("submit", function (e) {
      e.preventDefault();
      var email = pcEmail.value.trim();
      if (!email || !socket || socket.readyState !== WebSocket.OPEN) return;
      pcErr.textContent = "";
      socket.send(JSON.stringify({ action: "identify", name: pcName.value.trim(), email: email }));
    });

    endedNew.addEventListener("click", function () {
      endedView.classList.remove("show");
      stopped = false;
      updateGate();     // restore input/pre-chat view
      connect();        // fresh socket → server returns a brand-new conversation
    });

    // --- status line: presence, overridden transiently by "typing…" ---
    var operatorOnline = null;
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

    // --- WebSocket ---
    var socket;
    function connect() {
      if (!siteKey) { hsub.textContent = "unavailable"; return; }
      socket = new WebSocket(wsUrl());
      socket.onopen = function () { refreshStatus(); };
      socket.onclose = function () {
        if (stopped) return;  // chat was ended by the operator — don't reconnect
        hsub.textContent = "reconnecting…";
        setTimeout(connect, 1500);
      };
      socket.onmessage = function (e) {
        var data = JSON.parse(e.data);
        switch (data.type) {
          case "welcome":
            setToken(data.token);
            identified = !!data.identified;
            updateGate();
            break;
          case "identified":
            identified = true;
            updateGate();
            input.focus();
            break;
          case "identify_error":
            pcErr.textContent = data.message || "Please try again.";
            break;
          case "ended":
            stopped = true;
            prechat.classList.remove("show");
            row.classList.add("hidden");
            endedView.classList.add("show");
            try { socket.close(); } catch (e) {}
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

    // --- outgoing typing (debounced) ---
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

    // --- helpers ---
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
  }
})();
