/*
 * Operator dashboard client — Phase 3.
 *
 * Extracted from operator.html (was inline) and extended with presence dots,
 * typing indicators, unread badges, and browser + sound notifications.
 * Message-type strings mirror chat/events.py (the backend's protocol source).
 */
(function () {
  "use strict";

  var statusEl = document.getElementById("status");
  var listEl = document.getElementById("list");
  var threadEl = document.getElementById("thread");
  var replyEl = document.getElementById("reply");
  var typingEl = document.getElementById("typing");

  var convs = {};      // id -> conversation summary
  var unread = {};     // id -> count
  var online = {};     // id -> visitor-online bool
  var currentId = null;
  var baseTitle = document.title;

  var wsUrl = (location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws/operator/";
  var socket;

  function connect() {
    socket = new WebSocket(wsUrl);
    socket.onopen = function () { statusEl.textContent = "· connected"; };
    socket.onclose = function () { statusEl.textContent = "· reconnecting…"; setTimeout(connect, 1500); };
    socket.onmessage = onMessage;
  }

  function onMessage(e) {
    var data = JSON.parse(e.data);
    switch (data.type) {
      case "conversations":
        convs = {}; online = {};
        data.conversations.forEach(function (c) { convs[c.id] = c; online[c.id] = !!c.online; });
        renderList();
        break;
      case "conversation_update":
        var c = data.conversation;
        convs[c.id] = c;
        if (c.id !== currentId && c.last_role === "visitor") {
          unread[c.id] = (unread[c.id] || 0) + 1;
          notify("Visitor " + c.visitor, c.last_body);
          beep();
        }
        renderList();
        break;
      case "history":
        if (data.conversation_id === currentId) renderThread(data.messages);
        break;
      case "message":
        if (data.message.conversation_id === currentId) {
          hideTyping();
          appendMsg(data.message);
          if (document.hidden && data.message.role === "visitor") { notify("New message", data.message.body); beep(); }
        }
        break;
      case "typing":
        if (data.conversation_id === currentId && data.role === "visitor") {
          data.typing ? showTyping() : hideTyping();
        }
        break;
      case "presence":
        if (data.scope === "visitor" && data.conversation_id != null) {
          online[data.conversation_id] = data.online;
          renderList();
        }
        break;
    }
  }

  function renderList() {
    var items = Object.values(convs).sort(function (a, b) {
      return (b.last_message_at || "").localeCompare(a.last_message_at || "");
    });
    listEl.innerHTML = "";
    var totalUnread = 0;
    items.forEach(function (c) {
      totalUnread += unread[c.id] || 0;
      var div = document.createElement("div");
      div.className = "conv" + (c.id === currentId ? " active" : "");
      var who = document.createElement("div");
      who.className = "who";
      if (online[c.id]) { var dot = document.createElement("span"); dot.className = "dot"; who.appendChild(dot); }
      who.appendChild(document.createTextNode("Visitor " + c.visitor));
      if (unread[c.id]) {
        var b = document.createElement("span"); b.className = "badge"; b.textContent = unread[c.id]; who.appendChild(b);
      }
      var prev = document.createElement("div");
      prev.className = "preview";
      prev.textContent = (c.last_role === "operator" ? "You: " + c.last_body : c.last_body) || "(no messages yet)";
      div.appendChild(who); div.appendChild(prev);
      div.onclick = function () { openConv(c.id); };
      listEl.appendChild(div);
    });
    document.title = totalUnread ? "(" + totalUnread + ") " + baseTitle : baseTitle;
  }

  function openConv(id) {
    currentId = id;
    unread[id] = 0;
    hideTyping();
    renderList();
    threadEl.innerHTML = "";
    replyEl.disabled = false;
    replyEl.placeholder = "Type a reply and press Enter…";
    replyEl.focus();
    unlockAudioAndNotify();
    socket.send(JSON.stringify({ action: "open", conversation_id: id }));
  }

  function renderThread(messages) { threadEl.innerHTML = ""; messages.forEach(appendMsg); }

  function appendMsg(m) {
    var div = document.createElement("div");
    div.className = "msg " + m.role;
    div.textContent = m.body;
    threadEl.appendChild(div);
    threadEl.scrollTop = threadEl.scrollHeight;
  }

  // --- incoming typing indicator ---
  var typingHideTimer;
  function showTyping() {
    typingEl.textContent = "Visitor is typing…";
    typingEl.style.display = "block";
    clearTimeout(typingHideTimer);
    typingHideTimer = setTimeout(hideTyping, 4000);
  }
  function hideTyping() { typingEl.style.display = "none"; clearTimeout(typingHideTimer); }

  // --- outgoing typing (debounced) ---
  var typingSent = false, typingIdle;
  function sendTyping(on) {
    if (currentId === null || !socket || socket.readyState !== WebSocket.OPEN || on === typingSent) return;
    typingSent = on;
    socket.send(JSON.stringify({ action: "typing", conversation_id: currentId, typing: on }));
  }
  replyEl.addEventListener("input", function () {
    sendTyping(true);
    clearTimeout(typingIdle);
    typingIdle = setTimeout(function () { sendTyping(false); }, 2500);
  });
  replyEl.addEventListener("keydown", function (e) {
    if (e.key !== "Enter") return;
    var body = replyEl.value.trim();
    if (!body || currentId === null || !socket || socket.readyState !== WebSocket.OPEN) return;
    socket.send(JSON.stringify({ action: "message", conversation_id: currentId, body: body }));
    replyEl.value = "";
    clearTimeout(typingIdle);
    sendTyping(false);
  });

  // --- notifications + sound ---
  var audioCtx;
  function unlockAudioAndNotify() {
    if ("Notification" in window && Notification.permission === "default") Notification.requestPermission();
    try {
      audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
      if (audioCtx.state === "suspended") audioCtx.resume();
    } catch (e) {}
  }
  function notify(title, body) {
    if (!("Notification" in window) || Notification.permission !== "granted") return;
    try { new Notification(title, { body: body || "" }); } catch (e) {}
  }
  function beep() {
    if (!audioCtx) return;  // unlocked on first conversation open (a user gesture)
    try {
      var o = audioCtx.createOscillator(), g = audioCtx.createGain();
      o.type = "sine"; o.frequency.value = 660;
      o.connect(g); g.connect(audioCtx.destination);
      g.gain.setValueAtTime(0.05, audioCtx.currentTime);
      g.gain.exponentialRampToValueAtTime(0.0001, audioCtx.currentTime + 0.3);
      o.start(); o.stop(audioCtx.currentTime + 0.3);
    } catch (e) {}
  }

  connect();
})();
