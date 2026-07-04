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
  var suggestEl = document.getElementById("suggest");
  var cannedMenuEl = document.getElementById("canned-menu");
  var threadHeaderEl = document.getElementById("thread-header");

  var canned = [];       // current conversation's saved replies
  var cannedItems = [];  // currently-filtered subset shown in the menu
  var cannedSel = -1;    // highlighted index

  var convs = {};      // id -> conversation summary
  var unread = {};     // id -> count
  var online = {};     // id -> visitor-online bool
  var currentId = null;
  var aiGlobal = false;   // is the AI feature configured at all (key present)?
  var suggesting = false; // a draft is currently streaming
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
        aiGlobal = !!data.ai_enabled;
        data.conversations.forEach(function (c) { convs[c.id] = c; online[c.id] = !!c.online; });
        renderList();
        updateSuggest();
        break;
      case "conversation_update":
        var c = data.conversation;
        convs[c.id] = c;
        if (c.id !== currentId && c.last_role === "visitor") {
          unread[c.id] = (unread[c.id] || 0) + 1;
          notify(c.name || ("Visitor " + c.visitor), c.last_body);
          beep();
        }
        renderList();
        if (c.id === currentId) renderThreadHeader();
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
      case "suggestion_start":
        if (data.conversation_id === currentId) replyEl.value = "";
        break;
      case "suggestion_delta":
        if (data.conversation_id === currentId) {
          replyEl.value += data.text;
          replyEl.scrollLeft = replyEl.scrollWidth;
        }
        break;
      case "suggestion_end":
        suggesting = false;
        suggestEl.textContent = "✨ Suggest";
        updateSuggest();
        replyEl.focus();
        break;
      case "suggestion_error":
        suggesting = false;
        updateSuggest();
        flashSuggestError(data.message);
        break;
      case "canned":
        if (data.conversation_id === currentId) canned = data.responses || [];
        break;
      case "conversation_removed":
        var rid = data.conversation_id;
        delete convs[rid]; delete unread[rid]; delete online[rid];
        if (rid === currentId) {
          currentId = null;
          threadEl.innerHTML = '<div id="empty">Select a conversation</div>';
          threadHeaderEl.classList.add("hidden");
          replyEl.disabled = true;
          replyEl.value = "";
          replyEl.placeholder = "Select a conversation to reply…";
          hideCannedMenu();
          updateSuggest();
        }
        renderList();
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
      who.appendChild(document.createTextNode(c.name || ("Visitor " + c.visitor)));
      if (c.site) { var st = document.createElement("span"); st.className = "site"; st.textContent = c.site; who.appendChild(st); }
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
    canned = [];        // refreshed by the "canned" message the server sends on open
    hideCannedMenu();
    hideTyping();
    renderList();
    threadEl.innerHTML = "";
    replyEl.disabled = false;
    replyEl.placeholder = "Type a reply and press Enter…";
    replyEl.focus();
    unlockAudioAndNotify();
    updateSuggest();
    renderThreadHeader();
    socket.send(JSON.stringify({ action: "open", conversation_id: id }));
  }

  function renderThreadHeader() {
    var c = convs[currentId];
    if (!c) { threadHeaderEl.classList.add("hidden"); return; }
    threadHeaderEl.innerHTML = "";
    var info = document.createElement("div");
    var name = document.createElement("div");
    name.className = "th-name";
    name.textContent = c.name || ("Visitor " + c.visitor);
    info.appendChild(name);
    var bits = [];
    if (c.email) bits.push(c.email);
    if (c.page_url) bits.push(c.page_url);
    if (bits.length) {
      var meta = document.createElement("div");
      meta.className = "th-meta";
      meta.textContent = bits.join("  ·  ");
      info.appendChild(meta);
    }
    threadHeaderEl.appendChild(info);
    var end = document.createElement("button");
    end.id = "end-chat";
    end.type = "button";
    end.textContent = "End chat";
    end.addEventListener("click", endCurrent);
    threadHeaderEl.appendChild(end);
    threadHeaderEl.classList.remove("hidden");
  }

  function endCurrent() {
    if (currentId === null || !socket || socket.readyState !== WebSocket.OPEN) return;
    if (!confirm("End this chat? The visitor will be thanked and it'll be removed from your inbox.")) return;
    socket.send(JSON.stringify({ action: "end", conversation_id: currentId }));
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
    updateCannedMenu();
    sendTyping(true);
    clearTimeout(typingIdle);
    typingIdle = setTimeout(function () { sendTyping(false); }, 2500);
  });
  replyEl.addEventListener("keydown", function (e) {
    // Canned-response menu navigation takes precedence over sending.
    if (cannedOpen()) {
      if (e.key === "ArrowDown") { e.preventDefault(); moveCanned(1); return; }
      if (e.key === "ArrowUp") { e.preventDefault(); moveCanned(-1); return; }
      if (e.key === "Escape") { e.preventDefault(); hideCannedMenu(); return; }
      if (e.key === "Enter" || e.key === "Tab") { e.preventDefault(); insertCanned(cannedSel); return; }
    }
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

  // --- AI suggested replies ---
  function updateSuggest() {
    if (!suggestEl) return;
    suggestEl.classList.toggle("hidden", !aiGlobal);
    var canSuggest = aiGlobal && currentId !== null &&
      convs[currentId] && convs[currentId].ai && !suggesting;
    suggestEl.disabled = !canSuggest;
  }

  var suggestErrTimer;
  function flashSuggestError(msg) {
    if (!suggestEl) return;
    suggestEl.textContent = "⚠ " + (msg || "AI error");
    clearTimeout(suggestErrTimer);
    suggestErrTimer = setTimeout(function () { suggestEl.textContent = "✨ Suggest"; }, 3000);
  }

  if (suggestEl) {
    suggestEl.addEventListener("click", function () {
      if (currentId === null || suggesting || !socket || socket.readyState !== WebSocket.OPEN) return;
      suggesting = true;
      suggestEl.textContent = "✨ Drafting…";
      updateSuggest();
      socket.send(JSON.stringify({ action: "suggest", conversation_id: currentId }));
    });
  }

  // --- canned responses (slash-command) ---
  function cannedOpen() {
    return !cannedMenuEl.classList.contains("hidden") && cannedItems.length > 0;
  }

  function updateCannedMenu() {
    var v = replyEl.value;
    if (v.charAt(0) !== "/" || canned.length === 0) { hideCannedMenu(); return; }
    var q = v.slice(1).toLowerCase();
    cannedItems = canned.filter(function (c) { return c.title.toLowerCase().indexOf(q) !== -1; });
    if (cannedItems.length === 0) { hideCannedMenu(); return; }
    cannedSel = 0;
    renderCannedMenu();
  }

  function renderCannedMenu() {
    cannedMenuEl.innerHTML = "";
    cannedItems.forEach(function (c, i) {
      var item = document.createElement("div");
      item.className = "canned-item" + (i === cannedSel ? " sel" : "");
      var t = document.createElement("div"); t.className = "t"; t.textContent = c.title;
      var b = document.createElement("div"); b.className = "b"; b.textContent = c.body;
      item.appendChild(t); item.appendChild(b);
      item.addEventListener("mousedown", function (e) { e.preventDefault(); insertCanned(i); });
      cannedMenuEl.appendChild(item);
    });
    cannedMenuEl.classList.remove("hidden");
  }

  function moveCanned(delta) {
    var n = cannedItems.length;
    cannedSel = (cannedSel + delta + n) % n;
    renderCannedMenu();
  }

  function insertCanned(i) {
    if (i < 0 || i >= cannedItems.length) return;
    replyEl.value = cannedItems[i].body;
    hideCannedMenu();
    replyEl.focus();
    clearTimeout(typingIdle);
    sendTyping(false);
  }

  function hideCannedMenu() {
    cannedMenuEl.classList.add("hidden");
    cannedItems = [];
    cannedSel = -1;
  }

  connect();
})();
