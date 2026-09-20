/* NEMESIS Web — client. Vanilla JS, aucune build step. */
(() => {
  "use strict";

  // ───────────────────────── état ─────────────────────────
  const S = {
    state: null,           // /api/state
    sessions: [],
    current: null,         // session id
    snapshot: null,
    ws: null,
    lastSeq: 0,
    events: [],
    toolRows: new Map(),   // call_id → element
    pendingRequest: null,
    models: [],
    thinkingEl: null,
    reconnectTimer: null,
    accessMode: "ask",
    slashIndex: 0,
  };

  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => Array.from(document.querySelectorAll(sel));
  const el = (tag, cls, text) => {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  };
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmtTime = (ts) => new Date((ts || Date.now() / 1000) * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  const fmtDur = (s) => (s < 60 ? `${s.toFixed(1)}s` : `${Math.floor(s / 60)}m${Math.round(s % 60)}s`);
  const fmtSize = (n) => (n < 1024 ? `${n} o` : n < 1048576 ? `${(n / 1024).toFixed(1)} Ko` : `${(n / 1048576).toFixed(1)} Mo`);

  async function api(path, opts = {}) {
    const res = await fetch(path, { headers: { "Content-Type": "application/json" }, ...opts, body: opts.body ? JSON.stringify(opts.body) : undefined });
    if (!res.ok) {
      let detail = res.statusText;
      try { detail = (await res.json()).detail || detail; } catch {}
      throw new Error(detail);
    }
    const ct = res.headers.get("content-type") || "";
    return ct.includes("json") ? res.json() : res.text();
  }

  function toast(msg, err = false) {
    const t = el("div", "toast" + (err ? " err" : ""), msg);
    $("#toasts").appendChild(t);
    setTimeout(() => t.remove(), 3500);
  }

  function renderMd(text) {
    try {
      const html = marked.parse(text || "", { breaks: true, gfm: true });
      return DOMPurify.sanitize(html, { ADD_ATTR: ["target"] });
    } catch {
      return `<p>${esc(text)}</p>`;
    }
  }

  // ───────────────────────── thème ─────────────────────────
  function applyTheme(t) {
    document.documentElement.dataset.theme = t;
    localStorage.setItem("nemesis.theme", t);
  }
  applyTheme(localStorage.getItem("nemesis.theme") || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"));
  $("#btn-theme").onclick = () => applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark");

  // ───────────────────────── layout ─────────────────────────
  $("#btn-collapse").onclick = () => { document.body.classList.add("sb-collapsed"); $("#btn-expand").classList.remove("hidden"); };
  $("#btn-expand").onclick = () => { document.body.classList.remove("sb-collapsed"); $("#btn-expand").classList.add("hidden"); };
  $("#btn-panel").onclick = () => { $("#panel").classList.toggle("hidden"); if (!$("#panel").classList.contains("hidden")) refreshPanel(); };
  $$(".tab").forEach((b) => (b.onclick = () => {
    $$(".tab").forEach((x) => x.classList.toggle("active", x === b));
    $$(".view").forEach((v) => v.classList.toggle("active", v.id === `view-${b.dataset.tab}`));
    if (b.dataset.tab === "trajectory") renderTrajectory();
  }));
  $$(".ptab").forEach((b) => (b.onclick = () => {
    $$(".ptab").forEach((x) => x.classList.toggle("active", x === b));
    $$(".pview").forEach((v) => v.classList.toggle("active", v.id === `ptab-${b.dataset.ptab}`));
    refreshPanel(b.dataset.ptab);
  }));
  $$(".mtab").forEach((b) => (b.onclick = () => {
    $$(".mtab").forEach((x) => x.classList.toggle("active", x === b));
    $$(".mview").forEach((v) => v.classList.toggle("active", v.id === `mtab-${b.dataset.mtab}`));
    loadSettingsTab(b.dataset.mtab);
  }));
  $$("[data-close]").forEach((b) => (b.onclick = () => $(`#${b.dataset.close}`).classList.add("hidden")));
  document.addEventListener("click", (e) => {
    $$(".dropdown.open").forEach((d) => { if (!d.contains(e.target)) d.classList.remove("open"); });
  });

  // ───────────────────────── sessions ─────────────────────────
  async function loadState() {
    S.state = await api("/api/state");
    $("#st-ws").textContent = S.state.workspace;
    $("#st-ws").title = S.state.workspace;
    $("#cfg-dir").textContent = S.state.config_dir;
    const menu = $("#access-menu");
    menu.innerHTML = "";
    S.state.access_modes.forEach((m) => {
      const it = el("div", "dd-item");
      it.dataset.mode = m.id;
      it.innerHTML = `<div>${esc(m.label)}</div><div class="dd-desc">${esc(m.desc)}</div>`;
      it.onclick = () => setAccess(m.id);
      menu.appendChild(it);
    });
    updateAccessUI();
  }

  async function loadSessions() {
    const r = await api("/api/sessions");
    S.sessions = r.sessions;
    renderSessionList();
  }

  function renderSessionList() {
    const list = $("#session-list");
    list.innerHTML = "";
    if (!S.sessions.length) list.appendChild(el("div", "muted small", "Aucune conversation."));
    S.sessions.forEach((s) => {
      const it = el("div", "session-item" + (s.id === S.current ? " active" : "") + (s.archived ? " archived" : ""));
      if (s.busy) it.appendChild(el("span", "s-busy"));
      it.appendChild(el("span", "s-title", s.title));
      const del = el("button", "icon-btn s-del", "✕");
      del.title = "Supprimer";
      del.onclick = async (e) => { e.stopPropagation(); if (!confirm("Supprimer cette conversation ?")) return; await api(`/api/sessions/${s.id}`, { method: "DELETE" }); if (S.current === s.id) { S.current = null; resetTimeline(); } await loadSessions(); };
      it.appendChild(del);
      it.onclick = () => openSession(s.id, s.archived);
      list.appendChild(it);
    });
  }

  $("#btn-new").onclick = () => { $("#new-sysprompt").checked = $("#sysprompt-toggle").checked; $("#modal-new").classList.remove("hidden"); $("#new-title").focus(); };
  $("#btn-new-confirm").onclick = async () => {
    const body = { title: $("#new-title").value.trim() || null, access_mode: $("#new-access").value, send_system_prompt: $("#new-sysprompt").checked };
    $("#modal-new").classList.add("hidden");
    $("#new-title").value = "";
    const s = await api("/api/sessions", { method: "POST", body });
    $("#sysprompt-toggle").checked = body.send_system_prompt;
    await loadSessions();
    openSession(s.id);
  };

  async function ensureSession() {
    if (S.current && !S.snapshot?.archived) return S.current;
    const s = await api("/api/sessions", { method: "POST", body: { access_mode: S.accessMode, send_system_prompt: $("#sysprompt-toggle").checked } });
    await loadSessions();
    await openSession(s.id);
    return s.id;
  }

  function resetTimeline() {
    const tl = $("#timeline");
    tl.querySelectorAll(":scope > :not(#empty-state)").forEach((n) => n.remove());
    $("#empty-state").classList.remove("hidden");
    S.toolRows.clear();
    S.events = [];
    S.lastSeq = 0;
    S.pendingRequest = null;
    setPending(null);
    setThinking(false);
    setBusy(false);
  }

  async function openSession(id, archived = false) {
    if (S.ws) { S.ws.onclose = null; S.ws.close(); S.ws = null; }
    clearTimeout(S.reconnectTimer);
    S.current = id;
    resetTimeline();
    renderSessionList();
    localStorage.setItem("nemesis.session", id);
    if (archived) {
      const data = await api(`/api/sessions/${id}`);
      S.snapshot = data;
      $("#session-title").textContent = data.title;
      $("#session-meta").textContent = "archivée (lecture seule)";
      (data.events || []).forEach(handleEvent);
      return;
    }
    connectWs();
  }

  function connectWs() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/ws/sessions/${S.current}?since=${S.lastSeq}`);
    S.ws = ws;
    ws.onmessage = (m) => { try { handleEvent(JSON.parse(m.data)); } catch (e) { console.error(e); } };
    ws.onclose = () => { if (S.ws === ws) { S.reconnectTimer = setTimeout(connectWs, 1500); } };
    ws.onerror = () => ws.close();
  }

  function wsSend(obj) {
    if (S.ws && S.ws.readyState === 1) { S.ws.send(JSON.stringify(obj)); return true; }
    return false;
  }

  // ───────────────────────── événements ─────────────────────────
  function handleEvent(ev) {
    if (ev.seq) { if (ev.seq <= S.lastSeq) return; S.lastSeq = ev.seq; }
    if (ev.type !== "pong") S.events.push(ev);
    switch (ev.type) {
      case "snapshot": applySnapshot(ev); break;
      case "ready": applyReady(ev); break;
      case "meta": applyMeta(ev); break;
      case "busy": setBusy(ev.busy); break;
      case "thinking": setThinking(ev.active, ev.message); break;
      case "user": addUser(ev); break;
      case "assistant": addAssistant(ev); break;
      case "tool_start": addToolStart(ev); break;
      case "tool_result": addToolResult(ev); break;
      case "auth_request": addAuthRequest(ev); break;
      case "input_request": addInputRequest(ev); break;
      case "input_resolved": resolveRequestCard(ev); break;
      case "system": addSystem(ev); break;
      case "error": addError(ev); break;
      case "summary": addSummary(ev); break;
      case "todo": addTodoCard(ev.items); refreshTodo(); break;
      case "clear": $("#timeline").querySelectorAll(":scope > :not(#empty-state)").forEach((n) => n.remove()); break;
      default: break;
    }
    if ($("#view-trajectory").classList.contains("active")) appendTrajectory(ev);
  }

  function applySnapshot(s) {
    S.snapshot = s;
    $("#session-title").textContent = s.title;
    S.accessMode = s.access_mode; updateAccessUI();
    if (s.model) $("#model-label").textContent = s.model;
    setBusy(s.busy);
    updateStats(s.stats);
    setConn(s.connected);
    if (s.pending_request && !S.pendingRequest) {
      // rejouer la demande en attente si non déjà affichée
      if (s.pending_request.type === "auth_request") addAuthRequest(s.pending_request, true);
      else addInputRequest(s.pending_request, true);
    }
    const meta = [];
    if (s.model) meta.push(s.model);
    $("#session-meta").textContent = meta.join(" · ");
    renderSessionList();
  }
  function applyReady(ev) {
    if (ev.model) { $("#model-label").textContent = ev.model; $("#st-model").textContent = ev.model; }
    $("#session-meta").textContent = `${ev.provider} · ${ev.target}`;
    $("#st-ws").textContent = ev.workspace;
    $("#sysprompt-toggle").checked = !!ev.send_system_prompt;
  }
  function applyMeta(ev) {
    if (ev.title) { $("#session-title").textContent = ev.title; loadSessions(); }
    if (ev.access_mode) { S.accessMode = ev.access_mode; updateAccessUI(); }
    if (ev.model) { $("#model-label").textContent = ev.model; $("#st-model").textContent = ev.model; }
    if ("connected" in ev) setConn(ev.connected);
  }
  function setConn(c) {
    const p = $("#conn-pill");
    p.classList.remove("ok", "bad", "neutral");
    p.classList.add(c === true ? "ok" : c === false ? "bad" : "neutral");
    p.querySelector(".pill-text").textContent = c === true ? "NEMAPI connecté" : c === false ? "NEMAPI hors ligne" : "NEMAPI";
  }
  function setBusy(b) {
    $("#btn-stop").classList.toggle("hidden", !b);
    $("#btn-send").classList.toggle("hidden", !!b);
    if (!b) setThinking(false);
    if (S.snapshot) { S.snapshot.busy = b; }
    const it = S.sessions.find((x) => x.id === S.current); if (it) { it.busy = b; renderSessionList(); }
  }
  function setThinking(active, message) {
    $("#thinking").classList.toggle("hidden", !active);
    if (message) $("#thinking .thinking-text").textContent = message;
    if (active) {
      if (!S.thinkingEl) {
        S.thinkingEl = el("div", "thinking-row");
        S.thinkingEl.innerHTML = `<span class="spinner"></span><span>${esc(message || "réflexion…")}</span>`;
      } else S.thinkingEl.querySelector("span:last-child").textContent = message || "réflexion…";
      $("#timeline").appendChild(S.thinkingEl);
      scrollBottom();
    } else if (S.thinkingEl) { S.thinkingEl.remove(); S.thinkingEl = null; }
  }
  function updateStats(st) {
    if (!st) return;
    $("#st-turns").textContent = `${st.turns} tour${st.turns > 1 ? "s" : ""}`;
    $("#st-tools").textContent = `${st.tool_calls} outil${st.tool_calls > 1 ? "s" : ""}`;
    $("#st-llm").textContent = `LLM ${fmtDur(st.llm_time || 0)}`;
  }

  // ───────────────────────── rendu timeline ─────────────────────────
  function push(node) {
    $("#empty-state").classList.add("hidden");
    const tl = $("#timeline");
    if (S.thinkingEl && S.thinkingEl.parentNode === tl) tl.insertBefore(node, S.thinkingEl); else tl.appendChild(node);
    scrollBottom();
  }
  function scrollBottom() {
    const tl = $("#timeline");
    const nearBottom = tl.scrollHeight - tl.scrollTop - tl.clientHeight < 200;
    if (nearBottom) tl.scrollTop = tl.scrollHeight;
  }
  function addUser(ev) {
    const m = el("div", "msg user");
    const b = el("div", "bubble" + (ev.command ? " command" : ""), ev.text);
    m.appendChild(b);
    const meta = el("div", "meta");
    meta.innerHTML = `<span>${fmtTime(ev.ts)}</span><button class="icon-btn" title="Copier" style="width:22px;height:22px;font-size:12px">⧉</button>`;
    meta.querySelector("button").onclick = () => navigator.clipboard.writeText(ev.text).then(() => toast("Copié"));
    m.appendChild(meta);
    push(m);
  }
  function addAssistant(ev) {
    const m = el("div", "msg assistant");
    const md = el("div", "md");
    md.innerHTML = renderMd(ev.text);
    md.querySelectorAll("a").forEach((a) => (a.target = "_blank"));
    m.appendChild(md);
    push(m);
  }
  const TOOL_ICONS = { bash: "$", read_file: "≡", write_file: "✎", edit: "✎", apply_patch: "⧉", grep: "⌕", glob: "⌕", list_dir: "▤", web_search: "⌂", web_fetch: "⇩", todo: "☑", git: "⑂", delete_file: "✕", mcp_call: "⚙", delegate_task: "⇶" };
  function toolSummary(tool, p) {
    if (!p || typeof p !== "object") return "";
    if (p.description) return p.description;
    if (tool === "bash") return p.command || "";
    if (tool === "read_file") return p.path || (p.paths || []).join(", ");
    if (tool === "write_file" || tool === "edit") return p.file_path || p.path || "";
    if (tool === "grep") return `${p.pattern} · ${p.path || "."}`;
    if (tool === "glob") return p.pattern || "";
    if (tool === "list_dir") return p.path || ".";
    if (tool === "web_search") return p.query || "";
    if (tool === "web_fetch") return p.url || "";
    if (tool === "todo") return `${p.action || "list"}${p.content ? " · " + p.content : ""}`;
    if (tool === "git") return p.action || "status";
    if (tool === "delete_file") return p.target_file || "";
    if (tool === "mcp_call") return `${p.server}.${p.tool}`;
    const k = Object.keys(p)[0];
    return k ? `${k}=${JSON.stringify(p[k]).slice(0, 80)}` : "";
  }
  function addToolStart(ev) {
    const row = el("div", "tool-row");
    row.dataset.callId = ev.call_id || "";
    const head = el("div", "tool-head");
    head.innerHTML = `<span class="tool-icon">${esc(TOOL_ICONS[ev.tool] || "⚒")}</span><span class="tool-name">${esc(ev.tool)}</span><span class="tool-desc" title="${esc(toolSummary(ev.tool, ev.params))}">${esc(toolSummary(ev.tool, ev.params))}</span><span class="risk ${esc(ev.risk || "medium")}">${esc(ev.risk || "medium")}</span><span class="tool-status running">en cours</span>`;
    head.onclick = () => row.classList.toggle("open");
    const body = el("div", "tool-body");
    body.innerHTML = `<div class="tb-section"><div class="tb-title">Paramètres</div><pre>${esc(JSON.stringify(ev.params, null, 2))}</pre></div>`;
    row.appendChild(head); row.appendChild(body);
    if (ev.call_id) S.toolRows.set(ev.call_id, row);
    push(row);
  }
  function addToolResult(ev) {
    let row = ev.call_id ? S.toolRows.get(ev.call_id) : null;
    if (!row) {
      // fallback : dernière ligne "en cours" pour cet outil
      row = $$(".tool-row").reverse().find((r) => r.querySelector(".tool-status.running") && r.querySelector(".tool-name").textContent === ev.tool);
    }
    if (!row) { addToolStart({ tool: ev.tool, params: {}, risk: "medium" }); row = $$(".tool-row").pop(); }
    const st = row.querySelector(".tool-status");
    st.className = "tool-status " + (ev.success ? "ok" : "fail");
    st.textContent = ev.success ? "ok" : "échec";
    const body = row.querySelector(".tool-body");
    const out = el("div", "tb-section tb-out");
    const title = el("div", "tb-title", "Résultat" + (ev.exit_code !== undefined && ev.exit_code !== null ? ` · exit ${ev.exit_code}` : ""));
    out.appendChild(title);
    if (ev.edits && Array.isArray(ev.edits) && ev.edits.length) {
      const d = el("div", "diff");
      ev.edits.forEach((e) => {
        (String(e.old_string ?? e.old ?? "").split("\n")).forEach((l) => { const s = el("span", "del", "- " + l); d.appendChild(s); });
        (String(e.new_string ?? e.new ?? "").split("\n")).forEach((l) => { const s = el("span", "add", "+ " + l); d.appendChild(s); });
      });
      out.appendChild(d);
    }
    const text = ev.output || ev.error || "(aucune sortie)";
    const pre = el("pre", "", text.length > 20000 ? text.slice(0, 20000) + `\n… (${text.length - 20000} caractères tronqués — voir panneau Sorties)` : text);
    out.appendChild(pre);
    body.appendChild(out);
    if (!ev.success) row.classList.add("open");
    if (ev.tool === "todo" && ev.items) refreshTodo();
    if (ev.tool === "write_file" || ev.tool === "edit" || ev.tool === "apply_patch" || ev.tool === "delete_file") refreshFiles();
    scrollBottom();
  }
  function addSystem(ev) {
    const row = el("div", "sys-row");
    if (ev.html) {
      row.innerHTML = DOMPurify.sanitize(ev.html, { ALLOWED_ATTR: ["style", "class"] });
      const pre = row.querySelector("pre"); if (pre) pre.className = "rich";
    } else {
      row.appendChild(el("div", "sys-text" + (ev.level ? " " + ev.level : ""), ev.text));
    }
    // marquer les outils refusés
    if (ev.text && /refusée/i.test(ev.text)) {
      const running = $$(".tool-status.running").pop();
      if (running) { running.className = "tool-status denied"; running.textContent = "refusé"; }
    }
    push(row);
  }
  function addError(ev) {
    const row = el("div", "error-row");
    const e = el("div", "err", ev.message);
    if (ev.trace) { const d = el("details"); d.appendChild(el("summary", "small", "trace")); d.appendChild(el("pre", "small", ev.trace)); e.appendChild(d); }
    row.appendChild(e);
    push(row);
  }
  function addSummary(ev) {
    const row = el("div", "summary-row");
    row.appendChild(el("div", "sum", `terminé en ${fmtDur(ev.elapsed)} · ${ev.tool_count} appel${ev.tool_count > 1 ? "s" : ""} d'outil`));
    push(row);
    if (S.snapshot?.stats) { S.snapshot.stats.turns += 1; S.snapshot.stats.tool_calls += ev.tool_count; updateStats(S.snapshot.stats); }
    refreshTodo();
    api(`/api/sessions/${S.current}`).then((s) => updateStats(s.stats)).catch(() => {});
  }
  function addTodoCard(items) {
    if (!items || !items.length) return;
    const row = el("div", "todo-card");
    const c = el("div", "card");
    c.appendChild(el("div", "card-title", "☑ Plan de travail"));
    items.forEach((it) => c.appendChild(todoItem(it)));
    row.appendChild(c);
    push(row);
  }
  function todoItem(it) {
    const d = el("div", "todo-item " + (it.status || "pending"));
    const tk = { pending: "○", in_progress: "◐", completed: "●", cancelled: "×" }[it.status] || "○";
    d.innerHTML = `<span class="tk">${tk}</span><span>${esc(it.content)}</span>`;
    return d;
  }

  // ───────────────────────── autorisation / entrées ─────────────────────────
  function setPending(req) {
    S.pendingRequest = req;
    const bar = $("#pending-bar");
    if (!req) { bar.classList.add("hidden"); bar.innerHTML = ""; return; }
    bar.classList.remove("hidden");
    bar.innerHTML = `<span>${req.type === "auth_request" ? `⚠ Autorisation requise pour <b>${esc(req.tool)}</b> — répondez y / n / a ci-dessus ou dans la zone de saisie.` : `⌨ L'agent attend une saisie (${esc(req.title || "input")}).`}</span><button id="pending-jump">voir</button>`;
    $("#pending-jump").onclick = () => { const c = document.querySelector(`[data-req="${req.request_id}"]`); if (c) c.scrollIntoView({ behavior: "smooth", block: "center" }); };
  }
  function respond(requestId, value) {
    if (!wsSend({ type: "respond", request_id: requestId, value })) api(`/api/sessions/${S.current}/respond`, { method: "POST", body: { request_id: requestId, value } }).catch((e) => toast(e.message, true));
  }
  function addAuthRequest(ev, replay = false) {
    if (document.querySelector(`[data-req="${ev.request_id}"]`)) return;
    const row = el("div", "auth-card");
    row.dataset.req = ev.request_id;
    const c = el("div", "card");
    c.innerHTML = `<div class="card-title">⚠ Autoriser <code>${esc(ev.tool)}</code> ? <span class="risk ${esc(ev.risk || "medium")}">${esc(ev.risk || "medium")}</span></div><pre>${esc(ev.tool === "bash" && ev.params?.command ? ev.params.command : JSON.stringify(ev.params, null, 2))}</pre><div class="actions"><button class="btn-allow">✓ Autoriser (y)</button><button class="btn-always">Toujours pour ${esc(ev.tool)} (a)</button><button class="btn-deny">✕ Refuser (n)</button></div>`;
    const decide = (v, label) => { respond(ev.request_id, v); markDecided(row, label); };
    c.querySelector(".btn-allow").onclick = () => decide("y", "autorisé");
    c.querySelector(".btn-always").onclick = () => decide("a", `autorisé pour la session`);
    c.querySelector(".btn-deny").onclick = () => decide("n", "refusé");
    row.appendChild(c);
    push(row);
    setPending(ev);
    if (!replay) document.title = "⚠ NEMESIS — autorisation requise";
  }
  function addInputRequest(ev, replay = false) {
    if (document.querySelector(`[data-req="${ev.request_id}"]`)) return;
    const row = el("div", "input-card");
    row.dataset.req = ev.request_id;
    const c = el("div", "card");
    c.innerHTML = `<div class="card-title">⌨ ${esc(ev.title || "Saisie demandée")}</div><input placeholder="${esc(ev.placeholder || "Votre réponse…")}" /><div class="actions"><button class="btn-allow">Envoyer</button><button class="btn-deny">Annuler</button></div>`;
    const inp = c.querySelector("input");
    const send = () => { respond(ev.request_id, inp.value); markDecided(row, `réponse : ${inp.value}`); };
    c.querySelector(".btn-allow").onclick = send;
    inp.onkeydown = (e) => { if (e.key === "Enter") send(); };
    c.querySelector(".btn-deny").onclick = () => { respond(ev.request_id, null); markDecided(row, "annulé"); };
    row.appendChild(c);
    push(row);
    setPending(ev);
    if (!replay) setTimeout(() => inp.focus(), 50);
  }
  function markDecided(row, label) {
    const c = row.querySelector(".card");
    c.classList.add("resolved");
    const a = c.querySelector(".actions"); if (a) a.replaceWith(el("div", "decision", label));
    const inp = c.querySelector("input"); if (inp) inp.disabled = true;
    setPending(null);
    document.title = "NEMESIS Web";
  }
  function resolveRequestCard(ev) {
    const row = document.querySelector(`[data-req="${ev.request_id}"]`);
    if (row && !row.querySelector(".resolved")) {
      const v = ev.value;
      markDecided(row, v === null ? "annulé" : v === "y" ? "autorisé" : v === "a" ? "autorisé pour la session" : v === "n" ? "refusé" : `réponse : ${v}`);
    }
    if (S.pendingRequest && S.pendingRequest.request_id === ev.request_id) setPending(null);
  }

  // ───────────────────────── composer ─────────────────────────
  const input = $("#input");
  function autosize() { input.style.height = "auto"; input.style.height = Math.min(input.scrollHeight, 240) + "px"; }
  input.addEventListener("input", () => { autosize(); updateSlashMenu(); });
  input.addEventListener("keydown", (e) => {
    const menu = $("#slash-menu");
    if (!menu.classList.contains("hidden")) {
      const items = $$(".slash-item");
      if (e.key === "ArrowDown") { e.preventDefault(); S.slashIndex = (S.slashIndex + 1) % items.length; highlightSlash(); return; }
      if (e.key === "ArrowUp") { e.preventDefault(); S.slashIndex = (S.slashIndex - 1 + items.length) % items.length; highlightSlash(); return; }
      if (e.key === "Tab" || (e.key === "Enter" && items.length)) { e.preventDefault(); pickSlash(items[S.slashIndex]?.dataset.name); return; }
      if (e.key === "Escape") { menu.classList.add("hidden"); return; }
    }
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
    if (e.key === "Escape" && S.snapshot?.busy) interrupt();
  });
  $("#btn-send").onclick = send;
  $("#btn-stop").onclick = interrupt;
  $$(".chip").forEach((c) => (c.onclick = () => { input.value = c.dataset.prompt; autosize(); send(); }));

  async function send() {
    const text = input.value.trim();
    if (!text) return;
    // Réponse rapide à une autorisation en attente via la zone de saisie
    if (S.pendingRequest) {
      const v = text.toLowerCase();
      if (S.pendingRequest.type === "auth_request" && ["y", "n", "a", "yes", "no", "always"].includes(v)) {
        respond(S.pendingRequest.request_id, v[0]);
        const row = document.querySelector(`[data-req="${S.pendingRequest.request_id}"]`);
        if (row) markDecided(row, v[0] === "y" ? "autorisé" : v[0] === "a" ? "autorisé pour la session" : "refusé");
        input.value = ""; autosize(); return;
      }
      if (S.pendingRequest.type === "input_request") {
        const rid = S.pendingRequest.request_id;
        respond(rid, text);
        const row = document.querySelector(`[data-req="${rid}"]`);
        if (row) markDecided(row, `réponse : ${text}`);
        input.value = ""; autosize(); return;
      }
    }
    if (S.snapshot?.archived) { toast("Session archivée : créez une nouvelle conversation.", true); return; }
    const id = await ensureSession();
    input.value = ""; autosize(); $("#slash-menu").classList.add("hidden");
    if (!wsSend({ type: "message", text })) await api(`/api/sessions/${id}/message`, { method: "POST", body: { text } }).catch((e) => toast(e.message, true));
  }
  function interrupt() {
    if (!S.current) return;
    if (!wsSend({ type: "interrupt" })) api(`/api/sessions/${S.current}/interrupt`, { method: "POST" });
  }

  // slash menu
  function updateSlashMenu() {
    const menu = $("#slash-menu");
    const v = input.value;
    if (!v.startsWith("/") || v.includes(" ") || v.includes("\n") || !S.state) { menu.classList.add("hidden"); return; }
    const q = v.slice(1).toLowerCase();
    const cmds = S.state.commands.filter((c) => c.name.startsWith(q));
    if (!cmds.length) { menu.classList.add("hidden"); return; }
    menu.innerHTML = "";
    cmds.forEach((c) => {
      const it = el("div", "slash-item");
      it.dataset.name = c.name;
      it.innerHTML = `<span class="sn">/${esc(c.name)}</span><span class="sd">${esc(c.description)}${c.usage ? " · " + esc(c.usage) : ""}</span>`;
      it.onmousedown = (e) => { e.preventDefault(); pickSlash(c.name); };
      menu.appendChild(it);
    });
    S.slashIndex = 0; highlightSlash();
    menu.classList.remove("hidden");
  }
  function highlightSlash() { $$(".slash-item").forEach((x, i) => x.classList.toggle("active", i === S.slashIndex)); }
  function pickSlash(name) { if (!name) return; input.value = "/" + name + " "; $("#slash-menu").classList.add("hidden"); input.focus(); autosize(); }

  // accès
  function updateAccessUI() {
    const m = S.state?.access_modes.find((x) => x.id === S.accessMode);
    $("#access-label").textContent = m ? m.label : S.accessMode;
    $$("#access-menu .dd-item").forEach((x) => x.classList.toggle("active", x.dataset.mode === S.accessMode));
  }
  $("#access-btn").onclick = (e) => { e.stopPropagation(); $("#dd-access").classList.toggle("open"); };
  function setAccess(mode) {
    S.accessMode = mode; updateAccessUI(); $("#dd-access").classList.remove("open");
    if (S.current && !S.snapshot?.archived) { if (!wsSend({ type: "access", mode })) api(`/api/sessions/${S.current}/access`, { method: "POST", body: { mode } }); }
  }

  // modèles
  $("#model-btn").onclick = async (e) => {
    e.stopPropagation();
    const dd = $("#dd-model"); dd.classList.toggle("open");
    if (dd.classList.contains("open")) await loadModels();
  };
  async function loadModels() {
    const menu = $("#model-menu");
    menu.innerHTML = `<div class="dd-item muted">Chargement…</div>`;
    const r = await api("/api/models").catch((e) => ({ models: [], error: e.message }));
    S.models = r.models || [];
    menu.innerHTML = "";
    if (!S.models.length) {
      const it = el("div", "dd-item muted", r.error ? `Erreur : ${r.error}` : "Aucun modèle retourné par NEMAPI (/v1/models).");
      menu.appendChild(it);
      const custom = el("div", "dd-item");
      custom.innerHTML = `<input placeholder="ID de modèle manuel… (Entrée)" style="width:100%" />`;
      custom.querySelector("input").onkeydown = (ev) => { if (ev.key === "Enter") { pickModel(ev.target.value.trim()); } };
      custom.onclick = (ev) => ev.stopPropagation();
      menu.appendChild(custom);
      return;
    }
    const cur = $("#model-label").textContent;
    S.models.forEach((m) => {
      const it = el("div", "dd-item" + (m.id === cur ? " active" : ""));
      it.innerHTML = `<div>${esc(m.display_name || m.id)}</div><div class="dd-desc">${esc(m.id)} · ${esc(m.owned_by || "")}</div>`;
      it.onclick = () => pickModel(m.id);
      menu.appendChild(it);
    });
  }
  async function pickModel(id) {
    if (!id) return;
    $("#dd-model").classList.remove("open");
    $("#model-label").textContent = id; $("#st-model").textContent = id;
    if (S.current && !S.snapshot?.archived) await api(`/api/sessions/${S.current}/model`, { method: "POST", body: { model: id } }).catch((e) => toast(e.message, true));
    else await api("/api/config", { method: "PUT", body: { model: id } }).catch((e) => toast(e.message, true));
    toast(`Modèle : ${id}`);
  }

  // ───────────────────────── trajectoire ─────────────────────────
  function trajLine(ev) {
    const d = el("div", "tj");
    let detail = "";
    switch (ev.type) {
      case "user": case "assistant": detail = ev.text; break;
      case "tool_start": detail = `${ev.tool} ${JSON.stringify(ev.params)}`; break;
      case "tool_result": detail = `${ev.tool} → ${ev.success ? "ok" : "fail"}\n${(ev.output || "").slice(0, 600)}`; break;
      case "auth_request": detail = `${ev.tool} (${ev.risk})`; break;
      case "input_resolved": detail = `${ev.request_id} = ${ev.value}`; break;
      case "system": detail = ev.text || ""; break;
      case "error": detail = ev.message; break;
      case "summary": detail = `${fmtDur(ev.elapsed)} · ${ev.tool_count} outils`; break;
      case "thinking": detail = `${ev.active ? "start" : "stop"} · ${ev.message}`; break;
      default: detail = JSON.stringify(Object.fromEntries(Object.entries(ev).filter(([k]) => !["type", "seq", "ts"].includes(k)))).slice(0, 400);
    }
    d.innerHTML = `<span class="t">#${ev.seq ?? "-"}</span><span class="t">${fmtTime(ev.ts)}</span><span class="k ${esc(ev.type)}">${esc(ev.type)}</span><span class="d">${esc(detail)}</span>`;
    return d;
  }
  function trajVisible(ev) {
    if (!$("#traj-filter-system").checked && ["system", "busy", "thinking", "meta", "snapshot", "clear"].includes(ev.type)) return false;
    if (!$("#traj-filter-tools").checked && ["tool_start", "tool_result"].includes(ev.type)) return false;
    return true;
  }
  function renderTrajectory() {
    const t = $("#trajectory"); t.innerHTML = "";
    S.events.filter(trajVisible).forEach((ev) => t.appendChild(trajLine(ev)));
    t.scrollTop = t.scrollHeight;
  }
  function appendTrajectory(ev) { if (trajVisible(ev)) { const t = $("#trajectory"); t.appendChild(trajLine(ev)); t.scrollTop = t.scrollHeight; } }
  $("#traj-filter-system").onchange = renderTrajectory;
  $("#traj-filter-tools").onchange = renderTrajectory;
  $("#btn-export").onclick = () => {
    const blob = new Blob([JSON.stringify({ session: S.snapshot, events: S.events }, null, 2)], { type: "application/json" });
    const a = el("a"); a.href = URL.createObjectURL(blob); a.download = `nemesis-${S.current || "session"}.json`; a.click();
  };

  // ───────────────────────── panneau droit ─────────────────────────
  let filesPath = "";
  function refreshPanel(tab) {
    tab = tab || $(".ptab.active")?.dataset.ptab;
    if (tab === "todo") refreshTodo();
    if (tab === "files") refreshFiles();
    if (tab === "outputs") refreshOutputs();
    if (tab === "stats") refreshStats();
  }
  async function refreshTodo() {
    const r = await api("/api/todo").catch(() => ({ items: [] }));
    const l = $("#todo-list"); l.innerHTML = "";
    if (!r.items.length) { l.appendChild(el("div", "muted small", "Aucune tâche.")); return; }
    r.items.forEach((it) => l.appendChild(todoItem(it)));
  }
  async function refreshFiles(path) {
    if (path !== undefined) filesPath = path;
    if ($("#panel").classList.contains("hidden") && path === undefined) return;
    const r = await api(`/api/workspace/tree?path=${encodeURIComponent(filesPath)}`).catch((e) => ({ entries: [], error: e.message }));
    $("#files-crumb").textContent = "/" + (r.path || "");
    $("#files-crumb").title = r.root || "";
    const l = $("#file-list"); l.innerHTML = "";
    if (filesPath) { const up = el("div", "fi", "↰ .."); up.onclick = () => refreshFiles(filesPath.split("/").slice(0, -1).join("/")); l.appendChild(up); }
    if (r.error) l.appendChild(el("div", "muted small", r.error));
    (r.entries || []).forEach((e) => {
      const it = el("div", "fi");
      it.innerHTML = `<span>${e.dir ? "▸" : "·"}</span><span class="ellipsis">${esc(e.name)}</span><span class="fs">${e.dir ? "" : fmtSize(e.size)}</span>`;
      it.onclick = () => (e.dir ? refreshFiles(e.path) : openFile(e.path));
      l.appendChild(it);
    });
  }
  async function openFile(path) {
    const r = await api(`/api/workspace/file?path=${encodeURIComponent(path)}`).catch((e) => ({ content: e.message }));
    $("#file-view").classList.remove("hidden");
    $("#file-view-name").textContent = path;
    $("#file-view-content").textContent = r.binary ? "(fichier binaire)" : r.content;
  }
  $("#btn-file-close").onclick = () => $("#file-view").classList.add("hidden");
  $("#btn-files-refresh").onclick = () => refreshFiles(filesPath);
  $("#btn-todo-refresh").onclick = refreshTodo;
  $("#btn-outputs-refresh").onclick = refreshOutputs;
  $("#btn-git-refresh").onclick = refreshStats;
  async function refreshOutputs() {
    const l = $("#outputs-list"); l.innerHTML = "";
    if (!S.current || S.snapshot?.archived) { l.appendChild(el("div", "muted small", "Aucune session active.")); return; }
    const r = await api(`/api/sessions/${S.current}/outputs`).catch(() => ({ outputs: [] }));
    if (!r.outputs.length) { l.appendChild(el("div", "muted small", "Aucune sortie bash enregistrée.")); return; }
    r.outputs.reverse().forEach((o) => {
      const it = el("div", "out-item");
      it.innerHTML = `<div><span class="${o.success ? "ok" : "fail"}" style="color:var(--${o.success ? "green" : "red"})">${o.success ? "✓" : "✗"}</span> #${o.id} · ${fmtSize(o.size)}</div><div class="oc">${esc(o.command)}</div>`;
      it.onclick = async () => {
        let pre = it.querySelector("pre");
        if (pre) { pre.remove(); return; }
        const txt = await api(`/api/sessions/${S.current}/outputs/${o.id}`).catch((e) => e.message);
        pre = el("pre", "", txt || "(vide)"); it.appendChild(pre);
      };
      l.appendChild(it);
    });
  }
  async function refreshStats() {
    const dl = $("#stats-list"); dl.innerHTML = "";
    if (S.current) {
      const s = await api(`/api/sessions/${S.current}`).catch(() => null);
      if (s) {
        const rows = [["Titre", s.title], ["Mode", s.access_mode], ["Modèle", s.model || "—"], ["Connexion", s.connected === true ? "ok" : s.connected === false ? "hors ligne" : "non testée"], ["Tours", s.stats?.turns ?? 0], ["Itérations LLM", s.stats?.llm_iterations ?? 0], ["Appels d'outils", s.stats?.tool_calls ?? 0], ["Échecs d'outils", s.stats?.tool_failures ?? 0], ["Temps LLM", fmtDur(s.stats?.llm_time || 0)], ["Temps total", fmtDur(s.stats?.elapsed_total || 0)], ["Outils autorisés", (s.authorized_tools || []).join(", ") || "—"]];
        rows.forEach(([k, v]) => { dl.appendChild(el("dt", "", k)); dl.appendChild(el("dd", "", String(v))); });
        updateStats(s.stats);
      }
    }
    const g = await api("/api/git").catch(() => ({ repo: false }));
    $("#git-info").textContent = g.repo ? `branche : ${g.branch}\n\n${g.status || "(propre)"}\n\n${g.log}` : "Le workspace n'est pas un dépôt git.";
  }

  // ───────────────────────── paramètres ─────────────────────────
  $("#btn-settings").onclick = async () => { $("#modal-settings").classList.remove("hidden"); loadSettingsTab("nemapi"); };
  async function loadSettingsTab(tab) {
    if (tab === "nemapi") {
      const c = await api("/api/config");
      $("#cfg-host").value = c.nemapi?.host || c.nemapi?.url || "127.0.0.1"; $("#cfg-port").value = c.nemapi?.port || 8090;
      $("#cfg-model").value = c.provider?.model || ""; $("#cfg-timeout").value = c.provider?.timeout || 180;
      $("#cfg-workspace").value = c.security?.workspace || "";
    } else if (tab === "tools") {
      const r = await api("/api/tools");
      $("#tools-list").innerHTML = r.tools.map((t) => `<div class="tool-card"><div class="tn"><span>${esc(t.name)}</span><span class="risk ${esc(t.risk)}">${esc(t.risk)}</span></div><div class="td">${esc(t.description)}</div><div class="td small">${esc(t.params.join(", "))}</div></div>`).join("");
    } else if (tab === "mcp") {
      await loadMcp();
    } else if (tab === "skills") {
      const sk = await api("/api/skills").catch(() => ({ skills: [] }));
      $("#skills-list").innerHTML = sk.skills.length ? sk.skills.map((s) => `<div class="list-item"><div class="li-main"><div>${esc(s.name || s.id || "?")}</div><div class="li-sub">${esc(s.description || s.path || "")}</div></div></div>`).join("") : `<div class="muted small">Aucune skill installée (/skills dans la CLI).</div>`;
      const ag = await api("/api/agents").catch(() => ({ agents: [] }));
      $("#agents-list").innerHTML = (ag.agents || []).length ? ag.agents.map((a) => `<div class="list-item"><div class="li-main"><div>${esc(a.name || "?")}</div><div class="li-sub">${esc(JSON.stringify(a).slice(0, 160))}</div></div></div>`).join("") : `<div class="muted small">Aucun agent A2A configuré (/agents).</div>`;
    } else if (tab === "prompt") {
      $("#sysprompt-view").textContent = await api("/api/system-prompt");
    } else if (tab === "commands") {
      $("#commands-list").innerHTML = (S.state?.commands || []).map((c) => `<div class="cmd-row"><span class="cn">/${esc(c.name)}</span><span>${esc(c.description)}${c.usage ? ` <span class="muted">· ${esc(c.usage)}</span>` : ""}</span></div>`).join("");
    }
  }
  $("#btn-cfg-test").onclick = async () => {
    $("#cfg-status").textContent = "test…";
    await api("/api/config", { method: "PUT", body: { host: $("#cfg-host").value, port: +$("#cfg-port").value || undefined } }).catch(() => {});
    const r = await api("/api/config/test", { method: "POST" });
    $("#cfg-status").textContent = r.ok ? `✓ connecté à ${r.target} (${r.model})` : `✗ injoignable${r.error ? " : " + r.error : ""}`;
    setConn(r.ok);
  };
  $("#btn-cfg-save").onclick = async () => {
    const body = { host: $("#cfg-host").value, port: +$("#cfg-port").value || undefined, model: $("#cfg-model").value || undefined, timeout: +$("#cfg-timeout").value || undefined, workspace: $("#cfg-workspace").value || undefined };
    await api("/api/config", { method: "PUT", body }).then(() => { toast("Configuration enregistrée"); $("#cfg-status").textContent = "enregistré"; loadState(); }).catch((e) => toast(e.message, true));
  };
  async function loadMcp() {
    const r = await api("/api/mcp").catch(() => ({ servers: {} }));
    const names = Object.keys(r.servers || {});
    $("#mcp-list").innerHTML = names.length ? "" : `<div class="muted small">Aucun serveur MCP.</div>`;
    names.forEach((n) => {
      const cfg = r.servers[n];
      const it = el("div", "list-item");
      it.innerHTML = `<div class="li-main"><div>${esc(n)} <span class="muted small">${esc(cfg.description || "")}</span></div><div class="li-sub">${esc(cfg.command || "")}</div></div><div class="li-actions"><button class="ghost-btn t">Tester</button><button class="ghost-btn d">Supprimer</button></div>`;
      it.querySelector(".t").onclick = async () => { $("#mcp-status").textContent = `test de ${n}…`; const x = await api(`/api/mcp/${encodeURIComponent(n)}/test`, { method: "POST" }); $("#mcp-status").textContent = `${x.ok ? "✓" : "✗"} ${x.message}`; };
      it.querySelector(".d").onclick = async () => { if (!confirm(`Supprimer ${n} ?`)) return; await api(`/api/mcp/${encodeURIComponent(n)}`, { method: "DELETE" }).catch((e) => toast(e.message, true)); loadMcp(); };
      $("#mcp-list").appendChild(it);
    });
  }
  $("#btn-mcp-add").onclick = async () => {
    const body = { name: $("#mcp-name").value.trim(), command: $("#mcp-cmd").value.trim(), description: $("#mcp-desc").value.trim() };
    if (!body.name || !body.command) return toast("Nom et commande requis", true);
    await api("/api/mcp", { method: "POST", body }).then(() => { toast("Serveur ajouté"); $("#mcp-name").value = $("#mcp-cmd").value = $("#mcp-desc").value = ""; loadMcp(); }).catch((e) => toast(e.message, true));
  };

  // ───────────────────────── init ─────────────────────────
  (async () => {
    try {
      await loadState();
      await loadSessions();
      const last = localStorage.getItem("nemesis.session");
      const live = S.sessions.find((s) => s.id === last && !s.archived);
      if (live) openSession(live.id);
      api("/api/config/test", { method: "POST" }).then((r) => setConn(r.ok)).catch(() => {});
      loadModels();
      setInterval(() => { if (S.ws && S.ws.readyState === 1) wsSend({ type: "ping" }); }, 25000);
      setInterval(loadSessions, 15000);
    } catch (e) {
      toast(`Erreur d'initialisation : ${e.message}`, true);
    }
  })();
})();
