/*
 * Live-chat widget loader — Phase 0 (walking skeleton).
 *
 * This is a deliberate PLACEHOLDER, not the real widget. Its only job is to prove
 * the embedding + WebSocket round-trip end to end:
 *   1. It figures out the backend origin from its own <script src> (so it works
 *      when embedded on any third-party page, not just same-origin).
 *   2. It injects a floating button + a tiny panel.
 *   3. It opens a WebSocket to /ws/echo/, sends a "ping" on connect, and shows
 *      every message the server broadcasts back.
 *
 * Deliberately NOT here yet: Shadow DOM style isolation, data-attribute config,
 * persistent visitor IDs, real chat UI. Those arrive in Phase 1/2.
 */
(function () {
  "use strict";

  // --- Work out where we were loaded from -------------------------------
  var currentScript =
    document.currentScript ||
    (function () {
      var scripts = document.getElementsByTagName("script");
      return scripts[scripts.length - 1];
    })();

  var backendOrigin;
  try {
    backendOrigin = new URL(currentScript.src).origin;
  } catch (e) {
    backendOrigin = window.location.origin; // same-origin fallback
  }
  var wsUrl = backendOrigin.replace(/^http/, "ws") + "/ws/echo/";

  // --- Minimal injected UI ---------------------------------------------
  var panelOpen = false;

  var button = document.createElement("button");
  button.textContent = "Chat";
  setStyle(button, {
    position: "fixed",
    bottom: "20px",
    right: "20px",
    zIndex: "2147483000",
    padding: "12px 18px",
    borderRadius: "24px",
    border: "none",
    background: "#2563eb",
    color: "#fff",
    fontFamily: "system-ui, sans-serif",
    fontSize: "14px",
    cursor: "pointer",
    boxShadow: "0 4px 12px rgba(0,0,0,0.2)",
  });

  var panel = document.createElement("div");
  setStyle(panel, {
    position: "fixed",
    bottom: "72px",
    right: "20px",
    zIndex: "2147483000",
    width: "280px",
    height: "320px",
    background: "#fff",
    border: "1px solid #e5e7eb",
    borderRadius: "10px",
    boxShadow: "0 8px 24px rgba(0,0,0,0.18)",
    display: "none",
    flexDirection: "column",
    overflow: "hidden",
    fontFamily: "system-ui, sans-serif",
  });

  var header = document.createElement("div");
  header.textContent = "Phase 0 echo — connecting…";
  setStyle(header, {
    padding: "10px 12px",
    background: "#f3f4f6",
    fontSize: "12px",
    color: "#374151",
    borderBottom: "1px solid #e5e7eb",
  });

  var log = document.createElement("div");
  setStyle(log, {
    flex: "1",
    padding: "10px 12px",
    overflowY: "auto",
    fontSize: "13px",
    color: "#111827",
  });

  var inputRow = document.createElement("div");
  setStyle(inputRow, {
    display: "flex",
    borderTop: "1px solid #e5e7eb",
  });

  var input = document.createElement("input");
  input.type = "text";
  input.placeholder = "Type and press Enter…";
  setStyle(input, {
    flex: "1",
    border: "none",
    padding: "10px 12px",
    fontSize: "13px",
    outline: "none",
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
    socket = new WebSocket(wsUrl);

    socket.addEventListener("open", function () {
      header.textContent = "Phase 0 echo — connected";
      socket.send(JSON.stringify({ message: "ping" }));
    });

    socket.addEventListener("message", function (event) {
      var data;
      try {
        data = JSON.parse(event.data);
      } catch (e) {
        data = { type: "raw", text: event.data };
      }
      if (data.type === "system") {
        addLine("• " + data.text, "#6b7280");
      } else {
        addLine((data.self ? "you: " : "echo: ") + data.text, data.self ? "#2563eb" : "#111827");
      }
    });

    socket.addEventListener("close", function () {
      header.textContent = "Phase 0 echo — disconnected, retrying…";
      setTimeout(connect, 1500);
    });
  }

  input.addEventListener("keydown", function (e) {
    if (e.key !== "Enter") return;
    var text = input.value.trim();
    if (!text || !socket || socket.readyState !== WebSocket.OPEN) return;
    socket.send(JSON.stringify({ message: text }));
    input.value = "";
  });

  connect();

  // --- helpers ----------------------------------------------------------
  function addLine(text, color) {
    var line = document.createElement("div");
    line.textContent = text;
    line.style.marginBottom = "6px";
    if (color) line.style.color = color;
    log.appendChild(line);
    log.scrollTop = log.scrollHeight;
  }

  function setStyle(el, styles) {
    for (var key in styles) el.style[key] = styles[key];
  }
})();
