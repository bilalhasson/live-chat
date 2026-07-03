/*
 * Live-chat widget loader — Phase 1.
 *
 * Real visitor-side chat: connects to /ws/visitor/ for a specific Site (identified
 * by data-site-key), remembers the visitor across reloads via a localStorage token,
 * replays history, and exchanges live messages with the operator.
 *
 * Still a plain injected-DOM placeholder UI — Shadow DOM style isolation and
 * data-attribute theming (colour/position/greeting) arrive in Phase 2.
 */
(function () {
  "use strict";

  var currentScript =
    document.currentScript ||
    (function () {
      var s = document.getElementsByTagName("script");
      return s[s.length - 1];
    })();

  var siteKey =
    (currentScript && currentScript.getAttribute("data-site-key")) ||
    window.LIVECHAT_SITE_KEY ||
    "";

  var backendOrigin;
  try {
    backendOrigin = new URL(currentScript.src).origin;
  } catch (e) {
    backendOrigin = window.location.origin;
  }

  var tokenKey = "livechat_token_" + siteKey;
  function getToken() { try { return localStorage.getItem(tokenKey) || ""; } catch (e) { return ""; } }
  function setToken(t) { try { localStorage.setItem(tokenKey, t); } catch (e) {} }

  function wsUrl() {
    var base = backendOrigin.replace(/^http/, "ws") + "/ws/visitor/";
    return base + "?site=" + encodeURIComponent(siteKey) + "&token=" + encodeURIComponent(getToken());
  }

  // --- Injected UI ------------------------------------------------------
  var panelOpen = false;

  var button = el("button", { textContent: "Chat" }, {
    position: "fixed", bottom: "20px", right: "20px", zIndex: "2147483000",
    padding: "12px 18px", borderRadius: "24px", border: "none", background: "#2563eb",
    color: "#fff", fontFamily: "system-ui, sans-serif", fontSize: "14px", cursor: "pointer",
    boxShadow: "0 4px 12px rgba(0,0,0,0.2)",
  });

  var panel = el("div", {}, {
    position: "fixed", bottom: "72px", right: "20px", zIndex: "2147483000",
    width: "300px", height: "400px", background: "#fff", border: "1px solid #e5e7eb",
    borderRadius: "10px", boxShadow: "0 8px 24px rgba(0,0,0,0.18)", display: "none",
    flexDirection: "column", overflow: "hidden", fontFamily: "system-ui, sans-serif",
  });

  var header = el("div", { textContent: "Chat with us" }, {
    padding: "10px 12px", background: "#2563eb", color: "#fff", fontSize: "14px",
  });

  var log = el("div", {}, {
    flex: "1", padding: "10px 12px", overflowY: "auto", fontSize: "14px", background: "#fafafa",
  });

  var inputRow = el("div", {}, { display: "flex", borderTop: "1px solid #e5e7eb" });
  var input = el("input", { type: "text", placeholder: "Type a message…" }, {
    flex: "1", border: "none", padding: "12px", fontSize: "14px", outline: "none",
  });

  inputRow.appendChild(input);
  panel.appendChild(header);
  panel.appendChild(log);
  panel.appendChild(inputRow);
  document.body.appendChild(panel);
  document.body.appendChild(button);

  button.addEventListener("click", function () {
    panelOpen = !panelOpen;
    panel.style.display = panelOpen ? "flex" : "none";
    if (panelOpen) input.focus();
  });

  // --- WebSocket --------------------------------------------------------
  var socket;
  function connect() {
    if (!siteKey) { header.textContent = "Chat unavailable (no site key)"; return; }
    socket = new WebSocket(wsUrl());

    socket.onopen = function () { header.textContent = "Chat with us"; };
    socket.onclose = function () { header.textContent = "Reconnecting…"; setTimeout(connect, 1500); };
    socket.onmessage = function (e) {
      var data = JSON.parse(e.data);
      if (data.type === "welcome") {
        setToken(data.token);
      } else if (data.type === "history") {
        log.innerHTML = "";
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
  function addMessage(m) {
    var mine = m.role === "visitor";
    var bubble = el("div", { textContent: m.body }, {
      maxWidth: "75%", padding: "8px 11px", borderRadius: "12px", marginBottom: "8px",
      fontSize: "14px", lineHeight: "1.35",
      background: mine ? "#2563eb" : "#fff",
      color: mine ? "#fff" : "#111827",
      border: mine ? "none" : "1px solid #e5e7eb",
      marginLeft: mine ? "auto" : "0",
    });
    log.appendChild(bubble);
    log.scrollTop = log.scrollHeight;
  }

  function el(tag, props, styles) {
    var node = document.createElement(tag);
    for (var p in props) node[p] = props[p];
    for (var s in styles) node.style[s] = styles[s];
    return node;
  }
})();
