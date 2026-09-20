(() => {
  'use strict';

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const state = {
    server: null,
    tools: [],
    tree: null,
    connected: false,
    busy: false,
    jobId: null,
    eventSource: null,
    toolCards: new Map(),
    pendingCards: new Map(),
    attached: [],
    slashIndex: 0,
    slashCommands: [
      ['/help', 'Afficher les commandes disponibles'],
      ['/status', 'État du moteur et du workspace'],
      ['/tools', 'Voir le registre d’outils NEMESIS'],
      ['/clear', 'Réinitialiser le fil courant'],
      ['/models', 'Lister les modèles NEMAPI'],
      ['/settings', 'Ouvrir les paramètres'],
    ],
  };

  const iconForTool = (tool) => ({
    read_file: '◫', read: '◫', write_file: '＋', edit: '✎', apply_patch: '✎', delete_file: '×',
    bash: '>_', grep: '⌕', glob: '⌕', list_dir: '⌁', web_search: '◎', web_fetch: '↗',
    git: '⑂', todo: '☷', delegate_task: '◇', mcp_call: '◈',
  }[tool] || '◆');

  const escapeHtml = (value) => String(value ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#039;');

  function renderMarkdown(text) {
    let source = String(text || '').replace(/\r\n/g, '\n');
    const codeBlocks = [];
    source = source.replace(/```(?:[\w+-]+)?\n?([\s\S]*?)```/g, (_, code) => {
      const index = codeBlocks.push(`<pre><code>${escapeHtml(code.trimEnd())}</code></pre>`) - 1;
      return `\u0000CODE${index}\u0000`;
    });
    let html = escapeHtml(source);
    html = html.replace(/\u0000CODE(\d+)\u0000/g, (_, index) => codeBlocks[Number(index)] || '');
    html = html.replace(/`([^`\n]+)`/g, '<span class="inline-code">$1</span>');
    html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1 ↗</a>');
    html = html.replace(/^### (.*)$/gm, '<strong>$1</strong>');
    html = html.replace(/^## (.*)$/gm, '<strong>$1</strong>');
    html = html.replace(/^# (.*)$/gm, '<strong>$1</strong>');
    html = html.replace(/^[-*] (.*)$/gm, '<li>$1</li>');
    html = html.replace(/(?:<li>.*<\/li>\n?)+/g, (list) => `<ul>${list}</ul>`);
    html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/__([^_]+)__/g, '<strong>$1</strong>');
    html = html.split(/\n{2,}/).map((paragraph) => paragraph.startsWith('<pre>') || paragraph.startsWith('<ul>') ? paragraph : `<p>${paragraph.replace(/\n/g, '<br>')}</p>`).join('');
    return html || '<span class="muted-line">(aucun texte)</span>';
  }

  function formatTime(timestamp) {
    const date = timestamp ? new Date(timestamp * 1000) : new Date();
    return date.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
  }

  function formatRelative(timestamp) {
    if (!timestamp) return '';
    const diff = Math.max(0, Date.now() - timestamp * 1000);
    if (diff < 60_000) return 'à l’instant';
    if (diff < 3_600_000) return `${Math.floor(diff / 60_000)} min`;
    return new Date(timestamp * 1000).toLocaleDateString('fr-FR', { day: '2-digit', month: 'short' });
  }

  async function api(path, options = {}) {
    const response = await fetch(path, { headers: { 'Content-Type': 'application/json', ...(options.headers || {}) }, ...options });
    let data = {};
    try { data = await response.json(); } catch (_) { /* empty response */ }
    if (!response.ok) throw new Error(data.error || `Erreur HTTP ${response.status}`);
    return data;
  }

  function toast(message, kind = 'info') {
    const stack = $('#toast-stack');
    const item = document.createElement('div');
    item.className = `toast ${kind}`;
    item.innerHTML = `<span class="toast-mark">${kind === 'error' ? '!' : kind === 'ok' ? '✓' : '◆'}</span><span>${escapeHtml(message)}</span>`;
    stack.appendChild(item);
    window.setTimeout(() => item.remove(), 4200);
  }

  function setBusy(value, jobId = null) {
    state.busy = Boolean(value);
    state.jobId = jobId;
    $('#send-btn').disabled = state.busy;
    $('#stop-btn').classList.toggle('hidden', !state.busy);
    $('#typing-row').classList.toggle('hidden', !state.busy);
    $('#composer-input').disabled = state.busy;
    if (state.busy) {
      $('#composer-input').placeholder = 'Tâche en cours — vous pouvez l’arrêter…';
    } else {
      $('#composer-input').placeholder = 'Décrivez ce que vous voulez construire…';
    }
    scrollChat();
  }

  function hideWelcome() {
    $('#welcome-state').classList.add('hidden');
  }

  function scrollChat(force = false) {
    const panel = $('#chat-scroll');
    const nearBottom = panel.scrollHeight - panel.scrollTop - panel.clientHeight < 160;
    if (force || nearBottom) panel.scrollTo({ top: panel.scrollHeight, behavior: 'smooth' });
  }

  function addMessage(text, role = 'assistant', timestamp = null) {
    if (!text) return;
    hideWelcome();
    const list = $('#message-list');
    const block = document.createElement('article');
    block.className = `message-block ${role}`;
    const isUser = role === 'user';
    block.innerHTML = `
      <div class="message-meta">
        <span class="message-avatar ${isUser ? 'user-avatar' : ''}">${isUser ? 'T' : 'N'}</span>
        <strong>${isUser ? 'Vous' : 'NEMESIS'}</strong>
        <span class="message-time">${formatTime(timestamp)}</span>
      </div>
      <div class="message-bubble">${isUser ? renderMarkdown(text) : renderMarkdown(text)}</div>`;
    list.appendChild(block);
    scrollChat(true);
    return block;
  }

  function setTyping(value) {
    $('#typing-row').classList.toggle('hidden', !value);
    if (value) scrollChat();
  }

  function prettyParams(params) {
    try { return JSON.stringify(params || {}, null, 2); } catch (_) { return String(params || ''); }
  }

  function findToolCard(payload) {
    if (payload.approval_id && state.toolCards.has(`approval:${payload.approval_id}`)) return state.toolCards.get(`approval:${payload.approval_id}`);
    const candidates = [...state.toolCards.values()].reverse();
    return candidates.find((card) => card.dataset.jobId === payload.job_id && card.dataset.tool === payload.tool && (card.dataset.status === 'pending' || card.dataset.status === 'running' || card.dataset.status === 'denied')) || null;
  }

  function updateCardStatus(card, status, output = '') {
    if (!card) return;
    card.dataset.status = status;
    card.classList.remove('success', 'denied', 'risk-high', 'risk-medium');
    if (status === 'success') card.classList.add('success');
    if (status === 'denied' || status === 'fail') card.classList.add('denied');
    const statusNode = $('.tool-status', card);
    const labels = { pending: ['waiting', 'En attente'], running: ['', 'En cours'], success: ['ok', 'Terminé'], fail: ['fail', 'Échec'], denied: ['fail', 'Refusé'] };
    const [klass, label] = labels[status] || labels.running;
    statusNode.className = `tool-status ${klass}`;
    statusNode.innerHTML = `${status === 'success' ? '✓' : status === 'fail' || status === 'denied' ? '×' : status === 'pending' ? '!' : '·'} ${label}<span class="tool-chevron">⌄</span>`;
    const outputNode = $('.tool-output', card);
    if (outputNode && output !== undefined) {
      outputNode.textContent = output || (status === 'running' ? 'Exécution de l’outil…' : '(aucune sortie)');
      outputNode.classList.toggle('empty', !output);
    }
    if (status !== 'pending') $('.approval-actions', card)?.remove();
  }

  function createToolCard(payload, status = 'running') {
    hideWelcome();
    const tool = payload.tool || 'tool';
    const risk = payload.risk || 'medium';
    const card = document.createElement('div');
    card.className = `tool-card risk-${risk} ${status === 'success' ? 'success' : ''}`;
    card.dataset.jobId = payload.job_id || '';
    card.dataset.tool = tool;
    card.dataset.status = status;
    const key = payload.approval_id ? `approval:${payload.approval_id}` : `tool:${payload.job_id || 'x'}:${tool}:${Date.now()}`;
    card.dataset.cardKey = key;
    card.innerHTML = `
      <div class="tool-head">
        <div class="tool-icon">${iconForTool(tool)}</div>
        <div class="tool-head-copy"><strong>${escapeHtml(tool.replace(/_/g, ' '))}</strong><small>${escapeHtml(payload.summary || `${tool.replace(/_/g, ' ')} — outil NEMESIS`)}</small></div>
        <div class="tool-status"><span class="tool-chevron">⌄</span></div>
      </div>
      <div class="tool-body"><pre class="tool-params">${escapeHtml(prettyParams(payload.params || {}))}</pre><pre class="tool-output empty">${status === 'running' ? 'Exécution de l’outil…' : '(en attente)'}</pre></div>`;
    if (status === 'pending') {
      card.classList.add('expanded');
      const actions = document.createElement('div');
      actions.className = 'approval-actions';
      actions.innerHTML = `<span class="approval-label">Autorisation requise</span><button class="deny-btn" data-decision="deny" data-approval="${escapeHtml(payload.approval_id || '')}">Refuser</button><button class="approve-btn always" data-decision="always" data-approval="${escapeHtml(payload.approval_id || '')}">Toujours</button><button class="approve-btn" data-decision="once" data-approval="${escapeHtml(payload.approval_id || '')}">Autoriser</button>`;
      card.appendChild(actions);
    }
    $('.tool-head', card).addEventListener('click', () => card.classList.toggle('expanded'));
    $('#message-list').appendChild(card);
    state.toolCards.set(key, card);
    if (payload.approval_id) state.pendingCards.set(payload.approval_id, card);
    if (status !== 'pending') card.classList.add('expanded');
    scrollChat(true);
    addActivity(payload, status === 'pending' ? 'approval' : 'tool');
    return card;
  }

  async function decideApproval(approvalId, decision) {
    try {
      await api(`/api/approvals/${encodeURIComponent(approvalId)}`, { method: 'POST', body: JSON.stringify({ decision }) });
      const card = state.pendingCards.get(approvalId);
      if (card) {
        $$('.approval-actions button', card).forEach((button) => { button.disabled = true; });
        const label = decision === 'deny' ? 'Refusé' : decision === 'always' ? 'Toujours autorisé' : 'Autorisé';
        $('.approval-label', card).textContent = label;
      }
      toast(decision === 'deny' ? 'Action refusée.' : 'Action autorisée.', decision === 'deny' ? 'info' : 'ok');
    } catch (error) { toast(error.message, 'error'); }
  }

  function addActivity(payload, kind = 'tool') {
    const list = $('#activity-list');
    $('.empty-pane', list)?.remove();
    const item = document.createElement('div');
    const success = payload.success === true;
    item.className = `activity-item ${success ? 'ok' : payload.status === 'fail' ? 'fail' : ''}`;
    const title = payload.tool ? payload.tool.replace(/_/g, ' ') : payload.text || payload.message || kind;
    const detail = payload.summary || (payload.output ? String(payload.output).split('\n')[0] : payload.message || '');
    item.innerHTML = `<span class="activity-mark">${kind === 'approval' ? '!' : success ? '✓' : '◆'}</span><span class="activity-copy"><strong>${escapeHtml(title)}</strong><small>${escapeHtml(detail)}</small></span><span class="activity-time">${formatTime(payload.ts || null)}</span>`;
    list.prepend(item);
    while (list.children.length > 60) list.lastElementChild.remove();
  }

  function handleEvent(eventName, payload) {
    payload = payload || {};
    if (eventName === 'user') { addMessage(payload.text, 'user'); addActivity({ text: 'Nouvelle tâche', summary: payload.text }, 'message'); return; }
    if (eventName === 'assistant') { setTyping(false); addMessage(payload.text, 'assistant'); addActivity({ text: 'Réponse agent', summary: payload.text }, 'agent'); return; }
    if (eventName === 'approval_required') { setTyping(false); createToolCard(payload, 'pending'); $('#plan-count').textContent = '1'; return; }
    if (eventName === 'approval_decision') {
      const card = state.pendingCards.get(payload.approval_id);
      if (card) {
        const label = payload.decision === 'deny' ? 'Refusé' : payload.decision === 'always' ? 'Toujours autorisé' : 'Autorisé';
        $('.approval-label', card).textContent = label;
        $$('.approval-actions button', card).forEach((button) => { button.disabled = true; });
        if (payload.decision === 'deny') updateCardStatus(card, 'denied', 'Exécution refusée par l’utilisateur.');
      }
      return;
    }
    if (eventName === 'tool_start') { setTyping(false); const card = findToolCard(payload) || createToolCard(payload, 'running'); card.dataset.status = 'running'; updateCardStatus(card, 'running'); return; }
    if (eventName === 'tool_result') {
      const card = findToolCard(payload) || createToolCard(payload, payload.success ? 'success' : 'fail');
      updateCardStatus(card, payload.denied ? 'denied' : payload.success ? 'success' : 'fail', payload.output || '');
      addActivity(payload, 'tool');
      setTyping(true);
      return;
    }
    if (eventName === 'tool_input') { toast('Cette commande attend une entrée. Utilisez le terminal local pour les commandes interactives.', 'info'); return; }
    if (eventName === 'done') { setTyping(false); setBusy(false); addActivity({ text: 'Tâche terminée', summary: `${payload.tool_count || 0} outil(s) · ${payload.elapsed || 0}s`, success: true }, 'done'); refreshFiles(); refreshPlan(); return; }
    if (eventName === 'cancelled') { setTyping(false); setBusy(false); addMessage('Tâche arrêtée à votre demande.', 'assistant'); return; }
    if (eventName === 'cancel_requested') { toast('Arrêt demandé…', 'info'); return; }
    if (eventName === 'error') { setTyping(false); setBusy(false); addMessage(`**Erreur** — ${payload.message || 'Une erreur est survenue.'}`, 'assistant'); toast(payload.message || 'Erreur agent', 'error'); return; }
    if (eventName === 'reset') { resetChatView(); return; }
    if (eventName === 'state') { applyServerState(payload); return; }
  }

  function connectEvents() {
    if (state.eventSource) state.eventSource.close();
    const source = new EventSource('/api/events');
    state.eventSource = source;
    ['user', 'assistant', 'approval_required', 'approval_decision', 'tool_start', 'tool_result', 'tool_input', 'done', 'cancelled', 'cancel_requested', 'error', 'reset', 'state'].forEach((name) => source.addEventListener(name, (event) => {
      try { handleEvent(name, JSON.parse(event.data)); } catch (_) { /* ignore malformed event */ }
    }));
    source.onerror = () => { state.connected = false; setTimeout(() => { if (state.eventSource === source) connectEvents(); }, 2500); };
  }

  function applyServerState(server) {
    if (!server || !server.session_id) return;
    state.server = server;
    state.connected = true;
    state.busy = Boolean(server.busy);
    if (Array.isArray(server.history)) renderRecent(server.history);
    updateEngineUI(server);
    if (server.active_job_id && server.busy) setBusy(true, server.active_job_id);
    $('#plan-count').textContent = server.pending_approvals?.length ? String(server.pending_approvals.length) : '0';
  }

  function updateEngineUI(server) {
    const connection = server.connection || 'not_tested';
    const isDemo = server.mode === 'demo';
    const dotClass = connection === 'offline' ? 'offline' : isDemo ? 'demo' : '';
    const label = isDemo ? 'Preview local' : connection === 'connected' ? 'NEMAPI connecté' : 'NEMAPI hors ligne';
    const detail = isDemo ? 'moteur local prêt' : `${server.model || 'modèle'} · ${server.endpoint || ''}`;
    $('#engine-label').textContent = label;
    $('#engine-detail').textContent = detail;
    $('#connection-label').textContent = label;
    $('#engine-card .status-dot').className = `status-dot ${dotClass}`;
    $('#connection-pill .status-dot').className = `status-dot ${dotClass}`;
    $('#mode-chip .status-dot').className = `status-dot ${dotClass}`;
    $('#mode-chip-label').textContent = isDemo ? 'Preview' : 'Live';
    $('#project-name').textContent = (server.workspace_display || server.workspace || 'workspace').split('/').pop() || 'workspace';
    if (server.busy) setBusy(true, server.active_job_id); else if (!state.busy) setBusy(false);
  }

  function resetChatView() {
    $('#message-list').innerHTML = '';
    $('#activity-list').innerHTML = '<div class="empty-pane"><span>◌</span><strong>En attente d’une tâche</strong><small>Les appels d’outils et résultats seront journalisés ici.</small></div>';
    $('#welcome-state').classList.remove('hidden');
    state.toolCards.clear(); state.pendingCards.clear();
    setBusy(false);
  }

  function renderHistory(items) {
    resetChatView();
    if (!Array.isArray(items) || !items.length) return;
    hideWelcome();
    items.forEach((item) => {
      if (item.kind === 'user') addMessage(item.text, 'user', item.ts);
      else if (item.kind === 'assistant') addMessage(item.text, 'assistant', item.ts);
      else if (item.kind === 'error') addMessage(`**Erreur** — ${item.text}`, 'assistant', item.ts);
      else if (item.kind === 'tool') {
        createToolCard({ job_id: item.job_id, tool: item.tool, params: item.params, risk: item.risk, summary: item.tool.replace(/_/g, ' ') }, item.success ? 'success' : 'fail');
        const card = findToolCard({ job_id: item.job_id, tool: item.tool });
        if (card) updateCardStatus(card, item.success ? 'success' : 'fail', item.output || '');
      } else if (item.kind === 'approval' && item.status === 'pending') {
        createToolCard(item, 'pending');
      }
    });
    scrollChat(false);
  }

  function renderRecent(items) {
    const list = $('#recent-list');
    const users = (items || []).filter((item) => item.kind === 'user');
    $('#history-count').textContent = users.length;
    if (!users.length) { list.innerHTML = '<div class="empty-recent">Vos conversations apparaîtront ici.</div>'; return; }
    list.innerHTML = users.slice(-7).reverse().map((item) => `<button class="recent-item"><span class="recent-icon">◌</span><span class="recent-title">${escapeHtml(item.text)}</span><span class="recent-time">${formatRelative(item.ts)}</span></button>`).join('');
  }

  async function refreshFiles() {
    try {
      state.tree = await api('/api/workspace/tree?path=.');
      renderTree(state.tree);
    } catch (error) { $('#file-tree').innerHTML = `<div class="tree-empty">${escapeHtml(error.message)}</div>`; }
  }

  function renderTree(root) {
    const tree = $('#file-tree');
    const filter = ($('#file-search-input').value || '').toLowerCase().trim();
    let fileCount = 0;
    const build = (node, isRoot = false) => {
      const children = (node.children || []).filter((child) => !filter || child.name.toLowerCase().includes(filter) || child.path.toLowerCase().includes(filter));
      if (!isRoot && filter && node.type === 'directory' && !children.length) return '';
      if (node.type === 'file') { fileCount += 1; return `<div class="tree-node file" data-path="${escapeHtml(node.path)}"><div class="tree-row" data-file="${escapeHtml(node.path)}"><span class="tree-chevron"></span><span class="tree-icon">·</span><span class="tree-label">${escapeHtml(node.name)}</span></div></div>`; }
      return `<div class="tree-node dir ${isRoot ? 'open' : ''}"><div class="tree-row"><span class="tree-chevron">›</span><span class="tree-icon">⌂</span><span class="tree-label">${escapeHtml(node.name || 'workspace')}</span></div><div class="tree-children">${children.map((child) => build(child)).join('') || '<div class="tree-empty">Dossier vide</div>'}</div></div>`;
    };
    tree.innerHTML = root ? build(root, true) : '<div class="tree-empty">Aucun fichier.</div>';
    $('#file-summary').textContent = `${fileCount} fichier${fileCount === 1 ? '' : 's'} visible${fileCount === 1 ? '' : 's'}`;
    $$('.tree-node.dir > .tree-row', tree).forEach((row) => row.addEventListener('click', (event) => { event.stopPropagation(); row.parentElement.classList.toggle('open'); }));
    $$('.tree-row[data-file]', tree).forEach((row) => row.addEventListener('click', () => openFile(row.dataset.file)));
  }

  async function openFile(path) {
    try {
      const file = await api(`/api/workspace/file?path=${encodeURIComponent(path)}`);
      if (file.binary) { toast('Ce fichier binaire ne peut pas être prévisualisé.', 'info'); return; }
      $('#file-preview').classList.remove('hidden');
      $('#preview-name').textContent = file.name;
      $('#preview-meta').textContent = `${file.language || 'text'} · ${file.size || 0} octets`;
      $('#preview-content').textContent = file.content || '';
      $('#file-preview').dataset.content = file.content || '';
    } catch (error) { toast(error.message, 'error'); }
  }

  async function refreshPlan() {
    try {
      const data = await api('/api/todos');
      const list = $('#plan-list');
      if (!data.items?.length) { list.innerHTML = '<div class="empty-pane"><span>☷</span><strong>Aucun plan actif</strong><small>Les tâches créées par NEMESIS apparaîtront ici.</small></div>'; $('#plan-count').textContent = '0'; return; }
      $('#plan-count').textContent = String(data.items.length);
      list.innerHTML = data.items.map((item) => `<div class="plan-item ${escapeHtml(item.status || 'pending')}"><span class="plan-check">${item.status === 'completed' ? '✓' : item.status === 'in_progress' ? '·' : ''}</span><span class="plan-text">${escapeHtml(item.content || item.text || '')}</span></div>`).join('');
    } catch (_) { /* plan is optional */ }
  }

  async function loadTools() {
    try {
      const data = await api('/api/tools');
      state.tools = data.tools || [];
      const grid = $('#tool-stat-grid');
      const read = state.tools.filter((tool) => tool.risk === 'read').length;
      const write = state.tools.length - read;
      grid.innerHTML = `<div class="tool-stat"><strong>${state.tools.length}</strong><small>outils enregistrés</small></div><div class="tool-stat"><strong>${read}</strong><small>lecture directe</small></div><div class="tool-stat"><strong>${write}</strong><small>avec approbation</small></div>`;
    } catch (_) { /* keep dialog usable */ }
  }

  async function loadModels() {
    try {
      const data = await api('/api/models');
      const select = $('#model-select');
      const settingsModel = $('#settings-model');
      const models = data.models || [];
      select.innerHTML = models.map((model) => `<option value="${escapeHtml(model.id)}">${escapeHtml(model.display_name || model.id)}</option>`).join('') || '<option value="">Aucun modèle</option>';
      if (data.selected) { select.value = data.selected; settingsModel.value = data.selected; }
    } catch (_) { /* preview model already present */ }
  }

  async function sendMessage(text = null) {
    if (state.busy) { toast('Une tâche est déjà en cours.', 'info'); return; }
    const input = $('#composer-input');
    let message = text ?? input.value.trim();
    if (!message) return;
    if (state.attached.length) {
      const attachments = state.attached.map((item) => `--- ${item.name} ---\n${item.content}`).join('\n');
      message += `\n\n[Pièces jointes fournies par l’utilisateur]\n${attachments}`;
      state.attached = [];
      $('#attach-btn small').textContent = 'Joindre';
    }
    if (message.length > 8000) { toast('Le message est limité à 8 000 caractères.', 'error'); return; }
    input.value = ''; resizeInput(); updateCharCount(); hideSlashMenu();
    try {
      const response = await api('/api/chat', { method: 'POST', body: JSON.stringify({ message }) });
      setBusy(true, response.job_id);
      setTyping(true);
    } catch (error) { toast(error.message, 'error'); }
  }

  function resizeInput() {
    const input = $('#composer-input');
    input.style.height = 'auto';
    input.style.height = `${Math.min(190, Math.max(48, input.scrollHeight))}px`;
  }

  function updateCharCount() { $('#char-count').textContent = `${$('#composer-input').value.length.toLocaleString('fr-FR')} / 8 000`; }

  function showSlashMenu() {
    const query = $('#composer-input').value.slice(1).toLowerCase();
    if (!$('#composer-input').value.startsWith('/') || $('#composer-input').value.includes(' ')) { hideSlashMenu(); return; }
    const matches = state.slashCommands.filter(([command]) => command.slice(1).startsWith(query));
    const menu = $('#slash-menu');
    if (!matches.length) { hideSlashMenu(); return; }
    menu.innerHTML = matches.map(([command, description], index) => `<button class="slash-item ${index === state.slashIndex ? 'selected' : ''}" data-command="${command}"><strong>${command}</strong><small>${description}</small><span class="slash-hint">↵</span></button>`).join('');
    menu.classList.remove('hidden');
    $$('.slash-item', menu).forEach((item) => item.addEventListener('click', () => { $('#composer-input').value = `${item.dataset.command} `; hideSlashMenu(); $('#composer-input').focus(); }));
  }

  function hideSlashMenu() { $('#slash-menu').classList.add('hidden'); state.slashIndex = 0; }

  function openSettings() {
    const server = state.server || {};
    $('#settings-mode').value = server.mode || 'demo';
    const endpoint = String(server.endpoint || '127.0.0.1:8090').split(':');
    $('#settings-host').value = endpoint[0] === 'local preview' ? '127.0.0.1' : endpoint[0];
    $('#settings-port').value = endpoint[1] || '8090';
    $('#settings-model').value = server.model || 'qwen-chat';
    $('#settings-workspace').value = server.workspace || '';
    $('#settings-system-prompt').checked = server.send_system_prompt !== false;
    $('#settings-dialog').showModal();
    loadTools();
  }

  async function saveSettings(event) {
    event.preventDefault();
    const button = $('#save-settings');
    button.disabled = true; button.textContent = 'Connexion…';
    try {
      const server = await api('/api/settings', { method: 'POST', body: JSON.stringify({
        mode: $('#settings-mode').value,
        host: $('#settings-host').value,
        port: Number($('#settings-port').value || 8090),
        model: $('#settings-model').value,
        workspace: $('#settings-workspace').value,
        send_system_prompt: $('#settings-system-prompt').checked,
      }) });
      applyServerState(server); $('#settings-dialog').close(); toast(server.mode === 'demo' ? 'Preview local activé.' : server.connection === 'connected' ? 'NEMAPI connecté.' : 'Mode Live configuré, mais NEMAPI est hors ligne.', server.connection === 'connected' || server.mode === 'demo' ? 'ok' : 'error');
      refreshFiles(); refreshPlan(); loadModels();
    } catch (error) { toast(error.message, 'error'); }
    finally { button.disabled = false; button.textContent = 'Enregistrer'; }
  }

  function openPalette() {
    $('#command-palette').classList.remove('hidden');
    $('#palette-input').value = '';
    renderPalette();
    $('#palette-input').focus();
  }
  function closePalette() { $('#command-palette').classList.add('hidden'); }
  function renderPalette() {
    const query = $('#palette-input').value.toLowerCase();
    const items = state.slashCommands.filter(([command, desc]) => `${command} ${desc}`.toLowerCase().includes(query));
    $('#palette-list').innerHTML = items.map(([command, desc]) => `<div class="palette-command" data-command="${command}"><strong>${command}</strong><small>${desc}</small><kbd>↵</kbd></div>`).join('') || '<div class="tree-empty">Aucune commande.</div>';
    $$('.palette-command').forEach((item) => item.addEventListener('click', () => runCommand(item.dataset.command)));
  }
  function runCommand(command) {
    closePalette();
    if (command === '/settings') return openSettings();
    if (command === '/clear') return resetSession();
    if (command === '/models') return loadModels().then(() => toast('Modèles actualisés.', 'ok'));
    $('#composer-input').value = `${command} `; $('#composer-input').focus(); resizeInput(); updateCharCount();
  }

  async function resetSession() {
    if (!confirm('Réinitialiser le fil et les autorisations de cette session ?')) return;
    try { await api('/api/reset', { method: 'POST', body: '{}' }); toast('Session réinitialisée.', 'ok'); } catch (error) { toast(error.message, 'error'); }
  }

  async function attachFiles(files) {
    const selected = [...files].slice(0, 3);
    for (const file of selected) {
      if (file.size > 100_000) { toast(`${file.name} dépasse 100 Ko et a été ignoré.`, 'error'); continue; }
      try { state.attached.push({ name: file.name, content: await file.text() }); } catch (_) { /* ignore unreadable file */ }
    }
    if (state.attached.length) { $('#attach-btn small').textContent = `${state.attached.length} fichier${state.attached.length > 1 ? 's' : ''}`; toast('Fichier joint au prochain message.', 'ok'); }
  }

  function setInspectorTab(tab) {
    $$('.inspector-tab').forEach((button) => button.classList.toggle('active', button.dataset.tab === tab));
    $$('.inspector-pane').forEach((pane) => pane.classList.toggle('active', pane.id === `pane-${tab}`));
  }

  async function openResource(view) {
    $$('.nav-item[data-view]').forEach((button) => button.classList.toggle('active', button.dataset.view === view));
    if (view === 'workspace') {
      setInspectorTab('files');
      $('#inspector').classList.add('open');
      return;
    }
    const dialog = $('#resource-dialog');
    const list = $('#resource-list');
    const title = { history: 'Historique', agents: 'Agents A2A', skills: 'Skills installés' }[view] || 'Ressources';
    const eyebrow = { history: 'SESSION', agents: 'ORCHESTRATION', skills: 'CAPACITÉS' }[view] || 'NEMESIS';
    $('#resource-title').textContent = title;
    $('#resource-eyebrow').textContent = eyebrow;
    list.innerHTML = '<div class="resource-empty"><span class="mini-spinner"></span> Chargement…</div>';
    dialog.showModal();
    try {
      if (view === 'history') {
        const items = (state.server?.history || []).filter((item) => item.kind === 'user').slice().reverse();
        list.innerHTML = items.length ? items.map((item) => `<div class="resource-row"><span class="resource-symbol">◌</span><div><strong>${escapeHtml(item.text)}</strong><small>${formatTime(item.ts)} · tâche ${escapeHtml(item.job_id || '')}</small></div></div>`).join('') : '<div class="resource-empty">Aucune tâche dans cette session.</div>';
      } else if (view === 'agents') {
        const data = await api('/api/agents');
        list.innerHTML = data.agents?.length ? data.agents.map((agent) => `<div class="resource-row"><span class="resource-symbol">◇</span><div><strong>${escapeHtml(agent.name || agent.id || 'Agent')}</strong><small>${escapeHtml(agent.description || agent.model || 'Agent A2A disponible')}</small></div></div>`).join('') : '<div class="resource-empty">Aucun sous-agent configuré. Ajoutez-en dans <code>agents.json</code> pour activer la délégation A2A.</div>';
      } else {
        const data = await api('/api/skills');
        list.innerHTML = data.skills?.length ? data.skills.map((skill) => `<div class="resource-row"><span class="resource-symbol">✦</span><div><strong>${escapeHtml(skill.name)} <small>v${escapeHtml(skill.version || '1.0')}</small></strong><small>${escapeHtml(skill.description || 'Skill NEMESIS')}</small></div></div>`).join('') : '<div class="resource-empty">Aucun skill installé dans tools_library/.</div>';
      }
    } catch (error) { list.innerHTML = `<div class="resource-empty">${escapeHtml(error.message)}</div>`; }
  }

  function wireEvents() {
    $('#send-btn').addEventListener('click', () => sendMessage());
    $('#stop-btn').addEventListener('click', () => state.jobId && api(`/api/jobs/${state.jobId}/cancel`, { method: 'POST', body: '{}' }).catch((error) => toast(error.message, 'error')));
    $('#composer-input').addEventListener('input', () => { resizeInput(); updateCharCount(); showSlashMenu(); });
    $('#composer-input').addEventListener('keydown', (event) => {
      if (event.key === 'Enter' && !event.shiftKey) {
        if (!$('#slash-menu').classList.contains('hidden')) { const selected = $('.slash-item.selected'); if (selected) { event.preventDefault(); $('#composer-input').value = `${selected.dataset.command} `; hideSlashMenu(); return; } }
        event.preventDefault(); sendMessage();
      }
      if (event.key === 'Escape') hideSlashMenu();
      if (event.key === 'ArrowDown' && !$('#slash-menu').classList.contains('hidden')) { event.preventDefault(); state.slashIndex += 1; showSlashMenu(); }
      if (event.key === 'ArrowUp' && !$('#slash-menu').classList.contains('hidden')) { event.preventDefault(); state.slashIndex = Math.max(0, state.slashIndex - 1); showSlashMenu(); }
    });
    $('#message-list').addEventListener('click', (event) => { const button = event.target.closest('[data-approval]'); if (button) decideApproval(button.dataset.approval, button.dataset.decision); });
    $$('.prompt-card').forEach((card) => card.addEventListener('click', () => { $('#composer-input').value = card.dataset.prompt; resizeInput(); updateCharCount(); $('#composer-input').focus(); }));
    $('#new-task').addEventListener('click', resetSession);
    $$('.nav-item[data-view]').forEach((button) => button.addEventListener('click', () => openResource(button.dataset.view)));
    $('#open-settings').addEventListener('click', openSettings); $('#top-settings').addEventListener('click', openSettings); $('#engine-settings').addEventListener('click', openSettings); $('#mode-chip').addEventListener('click', openSettings);
    $('#close-resource').addEventListener('click', () => $('#resource-dialog').close());
    $('#resource-dialog').addEventListener('click', (event) => { if (event.target === $('#resource-dialog')) $('#resource-dialog').close(); });
    $('#model-select').addEventListener('change', async (event) => {
      if (!state.server || state.server.mode !== 'live') { toast('Le modèle local de preview ne se configure pas.', 'info'); return; }
      try { const server = await api('/api/settings', { method: 'POST', body: JSON.stringify({ mode: 'live', model: event.target.value, send_system_prompt: state.server.send_system_prompt }) }); applyServerState(server); toast('Modèle mis à jour.', 'ok'); } catch (error) { toast(error.message, 'error'); }
    });
    $('#settings-form').addEventListener('submit', saveSettings);
    $('#reset-session').addEventListener('click', () => { $('#settings-dialog').close(); resetSession(); });
    $$('.settings-tab').forEach((button) => button.addEventListener('click', () => { $$('.settings-tab').forEach((tab) => tab.classList.toggle('active', tab === button)); $$('.settings-content').forEach((content) => content.classList.toggle('active', content.id === `settings-${button.dataset.settingsTab}`)); }));
    $$('.inspector-tab').forEach((button) => button.addEventListener('click', () => setInspectorTab(button.dataset.tab)));
    $('#toggle-inspector').addEventListener('click', () => $('#inspector').classList.toggle('open'));
    $('#close-inspector').addEventListener('click', () => $('#inspector').classList.remove('open'));
    $('#refresh-files').addEventListener('click', refreshFiles); $('#refresh-plan').addEventListener('click', refreshPlan);
    $('#file-search-input').addEventListener('input', () => state.tree && renderTree(state.tree));
    $('#back-files').addEventListener('click', () => $('#file-preview').classList.add('hidden'));
    $('#copy-file').addEventListener('click', async () => { try { await navigator.clipboard.writeText($('#file-preview').dataset.content || ''); toast('Contenu copié.', 'ok'); } catch (_) { toast('Copie impossible dans ce navigateur.', 'error'); } });
    $('#clear-activity').addEventListener('click', () => { $('#activity-list').innerHTML = '<div class="empty-pane"><span>◌</span><strong>En attente d’une tâche</strong><small>Les appels d’outils et résultats seront journalisés ici.</small></div>'; });
    $('#attach-btn').addEventListener('click', () => $('#file-input').click()); $('#file-input').addEventListener('change', (event) => attachFiles(event.target.files));
    $('#context-btn').addEventListener('click', () => { const input = $('#composer-input'); input.value = `${input.value}@workspace `; input.focus(); resizeInput(); updateCharCount(); });
    $('#open-sidebar').addEventListener('click', () => { $('#sidebar').classList.add('open'); $('#sidebar-scrim').classList.add('open'); }); $('#close-sidebar').addEventListener('click', closeSidebar); $('#sidebar-scrim').addEventListener('click', closeSidebar);
    $('#palette-input').addEventListener('input', renderPalette); $('#command-palette').addEventListener('click', (event) => { if (event.target === $('#command-palette')) closePalette(); });
    $('#clear-recents').addEventListener('click', () => toast('Les sessions sont conservées côté serveur pendant cette session.', 'info'));
    document.addEventListener('keydown', (event) => { if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') { event.preventDefault(); openPalette(); } if ((event.metaKey || event.ctrlKey) && event.key === ',') { event.preventDefault(); openSettings(); } if (event.key === 'Escape') { closePalette(); } });
  }

  function closeSidebar() { $('#sidebar').classList.remove('open'); $('#sidebar-scrim').classList.remove('open'); }

  async function init() {
    wireEvents();
    connectEvents();
    try {
      const server = await api('/api/state');
      applyServerState(server); renderHistory(server.history); renderRecent(server.history); refreshFiles(); refreshPlan(); loadTools(); loadModels();
      if (server.pending_approvals?.length) server.pending_approvals.forEach((approval) => createToolCard(approval, 'pending'));
      if (server.busy) setBusy(true, server.active_job_id);
    } catch (error) { toast(`Serveur NEMESIS indisponible : ${error.message}`, 'error'); }
    resizeInput(); updateCharCount();
  }

  init();
})();
