// PolarisGate v2.3 — Application logic
var API = 'http://localhost:8002';

var lang = localStorage.getItem('polarisgate-lang') || 'en';
function t(key) { return (T[lang] && T[lang][key]) || (T.en[key] || key); }

function showToast(msg, type) {
  var c = document.getElementById('toast-container');
  var el = document.createElement('div');
  el.className = 'toast ' + type;
  el.textContent = msg;
  c.appendChild(el);
  setTimeout(function () { el.style.opacity = '0'; el.style.transition = 'opacity .3s'; }, 3000);
  setTimeout(function () { el.remove(); }, 3300);
}

function setLang(l) {
  lang = l;
  localStorage.setItem('polarisgate-lang', lang);
  applyStaticI18n();
  render();
}

function applyStaticI18n() {
  var el;
  el = document.getElementById('login-title'); if (el) el.textContent = t('brand');
  el = document.getElementById('login-subtitle'); if (el) el.textContent = t('subtitle');
  el = document.getElementById('login-email-label'); if (el) el.textContent = t('email');
  el = document.getElementById('login-password-label'); if (el) el.textContent = t('password');
  el = document.getElementById('login-btn'); if (el) el.textContent = t('login');
  el = document.getElementById('header-brand'); if (el) el.textContent = t('brand');
  el = document.getElementById('btn-logout'); if (el) el.textContent = t('logout');
}

var state = { tab: 'dashboard', sub: 'overview', _filter: null };
var _incidentCache = {};
var token = null;
function setTab(t, s) {
  state.tab = t;
  state.sub = s || 'overview';
  if (t !== 'dashboard' || s !== 'incidents') state._filter = null;
  _incidentCache = {};
  render();
}

async function handleLogin() {
  var email = document.getElementById('login-email').value;
  var pw = document.getElementById('login-password').value;
  var btn = document.getElementById('login-btn');
  var err = document.getElementById('login-error');
  btn.disabled = true;
  btn.textContent = t('loggingIn');
  err.textContent = '';
  try {
    var fd = new URLSearchParams();
    fd.append('username', email);
    fd.append('password', pw);
    var res = await fetch(API + '/auth/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: fd
    });
    if (!res.ok) {
      var j = await res.json().catch(function () { return {}; });
      throw new Error(j.detail || 'Login failed');
    }
    var json = await res.json();
    token = json.access_token;
    localStorage.setItem('polarisgate-token', token);
    showToast(t('loginSuccess'), 'success');
    document.getElementById('login-screen').classList.add('hidden');
    document.getElementById('dashboard-screen').classList.remove('hidden');
    render();
  } catch (e) {
    err.textContent = e.message === 'Invalid credentials' ? t('loginErr') : e.message;
  } finally {
    btn.disabled = false;
    btn.textContent = t('login');
  }
}

function handleLogout() {
  token = null;
  localStorage.removeItem('polarisgate-token');
  document.getElementById('login-screen').classList.remove('hidden');
  document.getElementById('dashboard-screen').classList.add('hidden');
  applyStaticI18n();
}
document.getElementById('login-password').addEventListener('keydown', function (e) {
  if (e.key === 'Enter') handleLogin();
});

async function get(endpoint) {
  try {
    var r = await fetch(API + endpoint, { headers: { Authorization: 'Bearer ' + token } });
    if (!r.ok) return null;
    return r.json();
  } catch (e) { return null; }
}
async function post(endpoint, body) {
  try {
    var r = await fetch(API + endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token },
      body: JSON.stringify(body)
    });
    if (!r.ok) {
      var j = await r.json().catch(function () { return {}; });
      throw new Error(j.detail || 'Request failed');
    }
    return r.json();
  } catch (e) { showToast(e.message, 'error'); return null; }
}
async function del(endpoint) {
  try {
    await fetch(API + endpoint, { method: 'DELETE', headers: { Authorization: 'Bearer ' + token } });
    return true;
  } catch (e) { return false; }
}

function escapeHtml(str) {
  if (str == null) return '';
  var div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function buildBadge(verdict, label) {
  var cls = '';
  if (verdict === 'blocked' || verdict === 'toxic') cls = 'badge-toxic';
  else if (verdict === 'pii') cls = 'badge-pii';
  else cls = 'badge-safe';
  return '<span class="badge ' + cls + '">' + escapeHtml(label) + '</span>';
}

function buildPipelineStatusBadge(status) {
  if (status === 'down') return '<span class="badge badge-toxic">' + t('pipelineStatusDown') + '</span>';
  if (status === 'degraded') return '<span class="badge badge-pii">' + t('pipelineStatusDegraded') + '</span>';
  return '<span class="badge badge-safe">' + t('pipelineStatusHealthy') + '</span>';
}

async function render() {
  if (!token) {
    token = localStorage.getItem('polarisgate-token');
    if (!token) return;
    document.getElementById('login-screen').classList.add('hidden');
    document.getElementById('dashboard-screen').classList.remove('hidden');
  }

  var tabs = [
    { k: 'dashboard', l: t('dashboard') },
    { k: 'policy', l: t('policies') },
    { k: 'compliance', l: t('compliance') },
    { k: 'admin', l: t('settings') }
  ];
  document.getElementById('main-tabs').innerHTML = tabs.map(function (tb) {
    return '<button class="tab' + (state.tab === tb.k ? ' active' : '') + '" onclick="setTab(\'' + tb.k + '\')">' + escapeHtml(tb.l) + '</button>';
  }).join('');

  var subTabs = {
    dashboard: [
      { k: 'overview', l: t('overview') },
      { k: 'incidents', l: t('incidents') },
      { k: 'models', l: t('models') }
    ],
    policy: [
      { k: 'guardrails', l: t('policyRules') },
      { k: 'testing', l: t('testContent') },
      { k: 'thresholds', l: t('domains') },
      { k: 'blocklist', l: t('blocklist') }
    ],
    compliance: [
      { k: 'audit', l: t('auditLogs') },
      { k: 'hallucination', l: t('hallucination') },
      { k: 'pipeline', l: t('pipeline') }
    ],
    admin: [
      { k: 'settings', l: t('general') },
      { k: 'apikeys', l: t('apiKeys') },
      { k: 'webhooks', l: t('webhooks') },
      { k: 'users', l: t('users') },
      { k: 'canary', l: t('canaryTokens') }
    ]
  };
  var st = subTabs[state.tab] || [];
  document.getElementById('sidebar').innerHTML = st.map(function (s) {
    return '<button class="sidebar-btn' + (state.sub === s.k ? ' active' : '') + '" onclick="setTab(\'' + state.tab + '\',\'' + s.k + '\')">' + escapeHtml(s.l) + '</button>';
  }).join('');

  var main = document.getElementById('main-content');
  main.innerHTML = '<div class="loading"><div class="spinner"></div>Loading...</div>';

  try {
    if (state.tab === 'dashboard') {
      if (state.sub === 'overview') await renderDashboard();
      else if (state.sub === 'incidents') await renderIncidents();
      else if (state.sub === 'models') await renderModels();
    } else if (state.tab === 'policy') {
      if (state.sub === 'testing') await renderPolicyTest();
      else if (state.sub === 'thresholds') await renderDomainThresholds();
      else if (state.sub === 'blocklist') await renderBlocklist();
      else await renderPolicyGuardrails();
    } else if (state.tab === 'compliance') {
      if (state.sub === 'hallucination') await renderHallucination();
      else if (state.sub === 'pipeline') await renderPipeline();
      else await renderAuditLogs();
    } else if (state.tab === 'admin') {
      if (state.sub === 'apikeys') await renderApiKeys();
      else if (state.sub === 'webhooks') await renderWebhooks();
      else if (state.sub === 'users') await renderUsers();
      else if (state.sub === 'canary') await renderCanary();
      else await renderSettings();
    } else {
      main.innerHTML = '<div class="card"><h2>' + escapeHtml(state.tab) + '</h2><p class="dim">' + t('comingSoon') + '</p></div>';
    }
  } catch (e) {
    main.innerHTML = '<div class="card"><h2>' + t('error') + '</h2><p style="color:#ef4444">' + escapeHtml(e.message) + '</p></div>';
  }
}

// ── Dashboard ────────────────────────────────────────────────────
async function renderDashboard() {
  var s = await get('/api/v1/dashboard/summary');
  var incidents = await get('/api/v1/dashboard/incidents?limit=5');
  var h = await get('/api/v1/hallucination/trend');
  var hallRate = t('nA');
  if (h && h.points && h.points.length) {
    var total = 0;
    h.points.forEach(function (p) { total += p.score || 0; });
    hallRate = (total / h.points.length).toFixed(1);
  } else {
    var det = await get('/api/v1/hallucination/detections?limit=100');
    if (det && det.detections && det.detections.length) hallRate = det.detections.length + ' total';
  }

  var canaryAlerts = await get('/api/v1/canary/alerts?limit=1');
  var canaryAlertCount = canaryAlerts ? canaryAlerts.length : 0;

  if (!s) {
    document.getElementById('main-content').innerHTML = '<div class="card"><h2>' + t('overview') + '</h2><p class="dim">' + t('noData') + '</p></div>';
    return;
  }

  var cards = [
    { label: t('traces24h'), value: s.total_traces_last_24h || 0, onclick: "setTab('dashboard','incidents')", color: '#4F8EF7' },
    { label: t('toxicityFlagged'), value: s.flagged_toxicity || 0, onclick: "state._filter='toxic';setTab('dashboard','incidents')", color: s.flagged_toxicity > 0 ? '#ef4444' : '#4F8EF7' },
    { label: t('piiDetected'), value: s.pii_leaks || 0, onclick: "state._filter='pii';setTab('dashboard','incidents')", color: s.pii_leaks > 0 ? '#f59e0b' : '#4F8EF7' },
    { label: t('activeModels'), value: s.active_models || 0, onclick: "setTab('dashboard','models')", color: '#4F8EF7' },
    { label: t('blockedWords'), value: s.blocked_count || 0, onclick: "state._filter='blocked';setTab('dashboard','incidents')", color: (s.blocked_count || 0) > 0 ? '#ef4444' : '#4F8EF7' },
    { label: t('safetyScore'), value: typeof s.fairness_score === 'number' ? (s.fairness_score * 100).toFixed(1) + '%' : (s.fairness_score || t('nA')), onclick: '', color: '#4F8EF7' },
    { label: t('hallucinationRate'), value: hallRate, onclick: "setTab('compliance','hallucination')", color: hallRate !== t('nA') ? '#4F8EF7' : '#f59e0b' },
    { label: t('canaryAlerts'), value: canaryAlertCount, onclick: "setTab('admin','canary')", color: canaryAlertCount > 0 ? '#ef4444' : '#4F8EF7' }
  ];

  var html = '<div class="summary-grid">';
  cards.forEach(function (card) {
    var clickable = card.onclick ? ' onclick="' + card.onclick + '"' : '';
    html += '<div class="summary-card"' + clickable + '><div class="label">' + escapeHtml(card.label) + '</div><div class="value" style="color:' + card.color + '">' + card.value + '</div></div>';
  });
  html += '</div>';

  _incidentCache = {};
  html += '<div class="card"><h2>' + t('recentIncidents') + '</h2><p class="dim mb" style="font-size:12px">' + t('expandForDetails') + '</p>';
  html += '<table><thead><tr><th>' + t('traceId') + '</th><th>' + t('verdict') + '</th><th>' + t('reason') + '</th><th>' + t('time') + '</th></tr></thead><tbody>';
  (incidents || []).forEach(function (i, idx) {
    var verdict = i.blocklisted ? 'blocked' : i.toxic ? 'toxic' : i.pii_detected ? 'pii' : 'clean';
    var label = i.blocklisted ? t('blockedVerdict') : i.toxic ? t('toxicVerdict') : i.pii_detected ? t('piiVerdict') : t('cleanVerdict');
    var piiTypes = (i.pii_types || []).join(',');
    _incidentCache[idx] = { traceId: i.trace_id || '', verdict: verdict, score: i.toxic_score || 0, reason: i.reason || '', timestamp: i.timestamp || '', piiTypes: piiTypes };
    html += '<tr class="incident-row" onclick="showIncidentDetail(' + idx + ')"><td class="mono-sm">' + escapeHtml((i.trace_id || '').toString().slice(0, 8)) + '...</td><td>' + buildBadge(verdict, label) + '</td><td>' + escapeHtml(i.reason || '') + '</td><td class="dim-sm">' + escapeHtml(i.timestamp || '') + '</td></tr>';
  });
  if (!(incidents || []).length) html += '<tr><td colspan="4" class="dim">' + t('noIncidents') + '</td></tr>';
  html += '</tbody></table></div>';
  html += '<div id="incident-detail-panel"></div>';

  document.getElementById('main-content').innerHTML = html;
}

// ── Incident Explainability ──────────────────────────────────────
function showIncidentDetail(idx) {
  var d = _incidentCache[idx];
  if (!d) return;
  var html = '<div class="card" style="margin-top:16px;border:1px solid #4F8EF7;background:rgba(79,142,247,0.05)"><h2>' + t('incidentDetail') + '</h2>';
  html += '<div class="incident-detail-grid">';
  html += '<div class="detail-item"><strong>' + t('incidentTraceId') + ':</strong><span class="mono-sm">' + escapeHtml(d.traceId) + '</span></div>';
  html += '<div class="detail-item"><strong>' + t('incidentVerdict') + ':</strong>' + buildBadge(d.verdict, d.verdict) + '</div>';
  html += '<div class="detail-item"><strong>' + t('incidentScore') + ':</strong>' + escapeHtml(d.score) + '</div>';
  html += '<div class="detail-item"><strong>' + t('incidentReason') + ':</strong>' + escapeHtml(d.reason || '-') + '</div>';
  html += '<div class="detail-item"><strong>' + t('time') + ':</strong>' + escapeHtml(d.timestamp || '') + '</div>';
  html += '</div>';
  html += '<div style="margin-top:16px"><strong>' + t('incidentDetectors') + ':</strong>';
  html += '<div class="detector-bar">';
  html += '<span class="detector-tag' + (d.verdict === 'toxic' ? ' fired' : '') + '">' + t('detectorToxicity') + '</span>';
  html += '<span class="detector-tag' + (d.verdict === 'pii' ? ' fired' : '') + '">' + t('detectorPII') + (d.piiTypes ? ' (' + escapeHtml(d.piiTypes) + ')' : '') + '</span>';
  html += '<span class="detector-tag">' + t('detectorInjection') + '</span>';
  html += '<span class="detector-tag' + (d.verdict === 'blocked' ? ' fired' : '') + '">' + t('detectorBlocklist') + '</span>';
  html += '<span class="detector-tag">' + t('detectorCanary') + '</span>';
  html += '</div></div>';
  html += '<button class="filter-btn" onclick="closeIncident()" style="margin-top:12px">✕ Close</button></div>';
  document.getElementById('incident-detail-panel').innerHTML = html;
}

function closeIncident() {
  document.getElementById('incident-detail-panel').innerHTML = '';
}

async function renderIncidents() {
  var incidents = await get('/api/v1/dashboard/incidents?limit=30');
  var items = incidents || [];
  var flt = state._filter;
  var filtered = flt ? items.filter(function (i) {
    return flt === 'toxic' ? i.toxic : flt === 'pii' ? i.pii_detected : i.blocklisted;
  }) : items;

  var html = '<div class="card"><h2>' + t('incidents') + '</h2><p class="dim mb" style="font-size:12px">' + t('expandForDetails') + '</p>';
  html += '<div class="filter-bar">';
  html += '<button class="filter-btn' + (!flt ? ' active' : '') + '" onclick="state._filter=null;render()">' + t('all') + '</button>';
  html += '<button class="filter-btn' + (flt === 'toxic' ? ' active' : '') + '" onclick="state._filter=\'toxic\';render()">' + t('toxic') + '</button>';
  html += '<button class="filter-btn' + (flt === 'pii' ? ' active' : '') + '" onclick="state._filter=\'pii\';render()">' + t('pii') + '</button>';
  html += '<button class="filter-btn' + (flt === 'blocked' ? ' active' : '') + '" onclick="state._filter=\'blocked\';render()">' + t('blocked') + '</button>';
  html += '</div>';

  _incidentCache = {};
  html += '<table><thead><tr><th>' + t('traceId') + '</th><th>' + t('verdict') + '</th><th>' + t('score') + '</th><th>' + t('reason') + '</th><th>' + t('time') + '</th></tr></thead><tbody>';
  filtered.forEach(function (i, idx) {
    var verdict = i.blocklisted ? 'blocked' : i.toxic ? 'toxic' : i.pii_detected ? 'pii' : 'clean';
    var label = i.blocklisted ? t('blockedVerdict') : i.toxic ? t('toxicVerdict') : i.pii_detected ? t('piiVerdict') : t('cleanVerdict');
    var piiTypes = (i.pii_types || []).join(',');
    _incidentCache[idx] = { traceId: i.trace_id || '', verdict: verdict, score: i.toxic_score || 0, reason: i.reason || '', timestamp: i.timestamp || '', piiTypes: piiTypes };
    html += '<tr class="incident-row" onclick="showIncidentDetail(' + idx + ')"><td class="mono-sm">' + escapeHtml((i.trace_id || '').toString().slice(0, 8)) + '...</td><td>' + buildBadge(verdict, label) + '</td><td>' + (i.toxic_score != null ? i.toxic_score : '-') + '</td><td>' + escapeHtml(i.reason || '') + '</td><td class="dim-sm">' + escapeHtml(i.timestamp || '') + '</td></tr>';
  });
  if (!filtered.length) html += '<tr><td colspan="5" class="dim">' + t('noIncidentsFound') + '</td></tr>';
  html += '</tbody></table></div>';
  html += '<div id="incident-detail-panel"></div>';
  document.getElementById('main-content').innerHTML = html;
}

async function renderModels() {
  var models = await get('/api/v1/dashboard/models');
  var html = '<div class="card"><h2>' + t('monitoredModels') + '</h2><p class="dim mb">' + t('modelsDesc') + '</p>';
  html += '<table><thead><tr><th>' + t('modelId') + '</th><th>' + t('traceCount') + '</th><th>' + t('lastSeen') + '</th></tr></thead><tbody>';
  (models || []).forEach(function (m) {
    html += '<tr><td>' + escapeHtml(m.model_id) + '</td><td>' + (m.trace_count || 0) + '</td><td>' + escapeHtml(m.last_seen || t('never')) + '</td></tr>';
  });
  if (!(models || []).length) html += '<tr><td colspan="3" class="dim">' + t('noModels') + '</td></tr>';
  html += '</tbody></table></div>';
  document.getElementById('main-content').innerHTML = html;
}

// ── Guardrails Pipeline ───────────────────────────────────────────
async function renderPipeline() {
  var summary = await get('/api/v1/dashboard/summary');
  var incidents = await get('/api/v1/dashboard/incidents?limit=50');
  var canaryAlerts = await get('/api/v1/canary/alerts?limit=50');

  var total24h = summary ? (summary.total_traces_last_24h || 0) : 0;
  var blocked24h = summary ? (summary.blocked_count || 0) : 0;
  var canaryAlertCount = canaryAlerts ? canaryAlerts.length : 0;

  var toxicityStatus = 'healthy', piiStatus = 'healthy', injectionStatus = 'healthy', blocklistStatus = 'healthy', redactionStatus = 'healthy';
  var canaryStatus = canaryAlertCount > 0 ? 'degraded' : 'healthy';

  var toxicCount = 0, piiCount = 0, blocklistCount = 0;
  (incidents || []).forEach(function (i) {
    if (i.toxic) toxicCount++;
    if (i.pii_detected) piiCount++;
    if (i.blocklisted) blocklistCount++;
  });
  if (toxicCount > 5) toxicityStatus = 'degraded';
  if (piiCount > 3) piiStatus = 'degraded';
  if (blocklistCount > 5) blocklistStatus = 'degraded';

  var html = '<div class="card"><h2>' + t('pipeline') + '</h2><p class="dim mb">' + t('pipelineDesc') + '</p>';
  html += '<div class="pipeline-stages">';
  var stages = [
    { name: t('pipelineStageToxicity'), status: toxicityStatus, count: toxicCount + ' flagged' },
    { name: t('pipelineStagePII'), status: piiStatus, count: piiCount + ' detected' },
    { name: t('pipelineStageInjection'), status: injectionStatus, count: 'Active' },
    { name: t('pipelineStageBlocklist'), status: blocklistStatus, count: blocklistCount + ' blocked' },
    { name: t('pipelineStageCanary'), status: canaryStatus, count: canaryAlertCount + ' alerts' },
    { name: t('pipelineStageRedaction'), status: redactionStatus, count: 'Active' }
  ];
  stages.forEach(function (stage) {
    html += '<div class="pipeline-stage-card stage-' + stage.status + '">';
    html += '<div class="pipeline-stage-name">' + escapeHtml(stage.name) + '</div>';
    html += '<div class="pipeline-stage-status">' + buildPipelineStatusBadge(stage.status) + '</div>';
    html += '<div class="pipeline-stage-count">' + escapeHtml(stage.count) + '</div>';
    html += '</div>';
  });
  html += '</div>';
  html += '<div class="card" style="margin-top:16px"><h3>' + t('pipelineMetrics') + '</h3>';
  html += '<div class="summary-grid" style="margin-top:12px">';
  html += '<div class="summary-card"><div class="label">' + t('checksToday') + '</div><div class="value" style="color:#4F8EF7">' + total24h + '</div></div>';
  html += '<div class="summary-card"><div class="label">' + t('blockedToday') + '</div><div class="value" style="color:' + (blocked24h > 0 ? '#ef4444' : '#4F8EF7') + '">' + blocked24h + '</div></div>';
  html += '<div class="summary-card"><div class="label">' + t('avgLatency') + '</div><div class="value" style="color:#4F8EF7">' + (total24h > 0 ? '< 50ms' : '-') + '</div></div>';
  html += '</div></div>';
  document.getElementById('main-content').innerHTML = html;
}

// ── Policies ──────────────────────────────────────────────────────
var policyEdits = [];

async function renderPolicyGuardrails() {
  var policies = await get('/api/v1/policies');
  var items = policies ? policies.policies : [];
  policyEdits = items.map(function (p) { return Object.assign({}, p); });
  var html = '<div class="card"><h2>' + t('contentSafetyPolicies') + '</h2><p class="dim mb">' + t('policyDesc') + '</p>';
  html += '<button class="btn-primary" onclick="savePolicies()" style="width:auto;padding:8px 20px;margin-bottom:16px">' + t('saveChanges') + '</button>';
  html += '<table><thead><tr><th>' + t('policyName') + '</th><th>' + t('type') + '</th><th>' + t('action') + '</th><th>' + t('severity') + '</th><th>' + t('enabled') + '</th></tr></thead><tbody>';
  policyEdits.forEach(function (p, i) {
    html += '<tr><td>' + escapeHtml(p.name) + '</td><td>' + escapeHtml(p.type) + '</td>';
    html += '<td><select onchange="policyEdits[' + i + '].action=this.value;rP()" class="form-select">';
    ['block', 'mask', 'flag', 'allow'].forEach(function (act) {
      html += '<option value="' + act + '"' + (p.action === act ? ' selected' : '') + '>' + act.charAt(0).toUpperCase() + act.slice(1) + '</option>';
    });
    html += '</select></td>';
    html += '<td><select onchange="policyEdits[' + i + '].severity=this.value;rP()" class="form-select">';
    ['critical', 'high', 'medium', 'low'].forEach(function (sev) {
      html += '<option value="' + sev + '"' + (p.severity === sev ? ' selected' : '') + '>' + sev.charAt(0).toUpperCase() + sev.slice(1) + '</option>';
    });
    html += '</select></td>';
    html += '<td><label class="toggle"><input type="checkbox"' + (p.enabled ? ' checked' : '') + ' onchange="policyEdits[' + i + '].enabled=this.checked;rP()"><span class="toggle-slider"></span></label></td></tr>';
  });
  html += '</tbody></table></div>';
  document.getElementById('main-content').innerHTML = html;
}
function rP() { renderPolicyGuardrails(); }
async function savePolicies() {
  var r = await post('/api/v1/policies', { policies: policyEdits });
  showToast(r ? t('policiesSaved') : t('saveFailed'), r ? 'success' : 'error');
}

async function renderPolicyTest() {
  var html = '<div class="card"><h2>' + t('testContentSafety') + '</h2><p class="dim mb">' + t('testDesc') + '</p>';
  html += '<div class="form-group"><textarea id="test-text" class="test-textarea" placeholder="' + escapeHtml(lang === 'fr' ? 'Collez le contenu à analyser...' : 'Paste content to analyze...') + '"></textarea></div>';
  html += '<div style="display:flex;gap:8px;margin-top:12px"><button class="btn-primary" onclick="runGuardrailTest()" id="test-btn" style="width:auto;padding:10px 24px">' + t('runAnalysis') + '</button><button class="btn-primary" onclick="runBatchTest()" id="batch-btn" style="width:auto;padding:10px 24px;background:linear-gradient(135deg,#7C8BB5,#4F8EF7)">' + t('batchTest') + '</button></div>';
  html += '<div id="test-result" style="margin-top:16px"></div></div>';
  document.getElementById('main-content').innerHTML = html;
}

async function runGuardrailTest() {
  var text = document.getElementById('test-text').value;
  if (!text) { showToast(t('enterText'), 'error'); return; }
  var btn = document.getElementById('test-btn');
  btn.disabled = true; btn.textContent = t('analyzing');
  var result = await post('/api/v1/guardrails/check', { text: text });
  btn.disabled = false; btn.textContent = t('runAnalysis');
  var el = document.getElementById('test-result');
  if (!result) { el.innerHTML = '<p style="color:#ef4444">' + t('unavailable') + '</p>'; return; }
  var html = '<div class="card" style="margin-top:16px"><h3>' + t('analysisResults') + '</h3>';
  html += '<p><strong>' + t('toxicContent') + ':</strong> ' + (result.toxic ? buildBadge('toxic', t('detected')) : buildBadge('clean', t('clean'))) + '</p>';
  html += '<p><strong>' + t('confidenceScore') + ':</strong> ' + (result.toxic_score != null ? result.toxic_score : t('nA')) + '</p>';
  if (result.reason) html += '<p><strong>' + t('reason') + ':</strong> ' + escapeHtml(result.reason) + '</p>';
  html += '<p><strong>' + t('piiDetectedLabel') + ':</strong> ' + (result.pii_detected ? buildBadge('pii', t('yes')) : buildBadge('clean', t('noneFound'))) + '</p>';
  html += '<p><strong>' + t('promptInjection') + ':</strong> ' + (result.injection_detected ? buildBadge('toxic', t('detected') + ' (' + (result.injection_score || 0).toFixed(2) + ')') : buildBadge('clean', t('noneDetected'))) + '</p>';
  html += '<p><strong>' + t('blocklistedLabel') + ':</strong> ' + (result.blocklisted ? buildBadge('toxic', t('blockedYes')) : buildBadge('clean', t('noneFound'))) + '</p>';
  if (result.pii_types && result.pii_types.length) html += '<p><strong>' + t('piiTypesFound') + ':</strong> ' + escapeHtml(result.pii_types.join(', ')) + '</p>';
  html += '<p style="margin-top:12px"><strong>' + t('redactedOutput') + ':</strong></p>';
  html += '<div class="redacted-box">' + escapeHtml(result.redacted_text || text) + '</div></div>';
  el.innerHTML = html;
}

async function runBatchTest() {
  var text = document.getElementById('test-text').value;
  if (!text) { showToast(t('enterTextFirst'), 'error'); return; }
  var lines = text.split('\n').filter(function (l) { return l.trim(); });
  var btn = document.getElementById('batch-btn');
  btn.disabled = true; btn.textContent = t('testing') + ' ' + lines.length + ' ' + t('items');
  var result = await post('/api/v1/guardrails/batch', { texts: lines });
  btn.disabled = false; btn.textContent = t('batchTest');
  var el = document.getElementById('test-result');
  if (!result) { el.innerHTML = '<p style="color:#ef4444">' + t('batchFailed') + '</p>'; return; }
  var html = '<div class="card" style="margin-top:16px"><h3>' + t('batchResults') + ' (' + result.total + ' ' + t('tested') + ')</h3>';
  html += '<table><thead><tr><th>#</th><th>Text</th><th>Toxic</th><th>PII</th></tr></thead><tbody>';
  (result.results || []).forEach(function (r, i) {
    html += '<tr><td>' + (i + 1) + '</td><td class="text-snippet">' + escapeHtml((lines[i] || '').slice(0, 60)) + '...</td><td>' + (r.toxic ? buildBadge('toxic', t('yes')) : buildBadge('clean', t('no'))) + '</td><td>' + (r.pii_detected ? buildBadge('pii', t('yes')) : buildBadge('clean', t('no'))) + '</td></tr>';
  });
  html += '</tbody></table></div>';
  el.innerHTML = html;
}

// ── Domain Thresholds / Blocklist / Audit / Hallucination ──────────
async function renderDomainThresholds() {
  var dt = await get('/api/v1/settings/domain-thresholds');
  var thresholds = dt ? (dt.thresholds || []) : [];
  var html = '<div class="card"><h2>' + t('domainThresholds') + '</h2><p class="dim mb">' + t('domainDesc') + '</p><div id="domain-list">';
  thresholds.forEach(function (t, i) {
    html += '<div class="domain-row"><span class="domain-label">' + escapeHtml(t.domain) + '</span>';
    html += '<select id="dt-severity-' + i + '" class="form-select"><option value="critical"' + (t.severity === 'critical' ? ' selected' : '') + '>Critical</option><option value="high"' + (t.severity === 'high' ? ' selected' : '') + '>High</option><option value="medium"' + (t.severity === 'medium' ? ' selected' : '') + '>Medium</option><option value="low"' + (t.severity === 'low' ? ' selected' : '') + '>Low</option></select>';
    html += '<select id="dt-tox-' + i + '" class="form-select"><option value="block"' + (t.toxicity_action === 'block' ? ' selected' : '') + '>Tox: Block</option><option value="flag"' + (t.toxicity_action === 'flag' ? ' selected' : '') + '>Tox: Flag</option><option value="allow"' + (t.toxicity_action === 'allow' ? ' selected' : '') + '>Tox: Allow</option></select>';
    html += '<select id="dt-pii-' + i + '" class="form-select"><option value="block"' + (t.pii_action === 'block' ? ' selected' : '') + '>PII: Block</option><option value="mask"' + (t.pii_action === 'mask' ? ' selected' : '') + '>PII: Mask</option><option value="flag"' + (t.pii_action === 'flag' ? ' selected' : '') + '>PII: Flag</option></select></div>';
  });
  html += '</div><button class="btn-primary" onclick="saveDomainThresholds()" style="width:auto;padding:10px 24px">' + t('saveDomainThresholds') + '</button></div>';
  document.getElementById('main-content').innerHTML = html;
}
async function saveDomainThresholds() {
  var dt = await get('/api/v1/settings/domain-thresholds');
  var items = dt ? (dt.thresholds || []) : [];
  var updated = items.map(function (t, i) { return { domain: t.domain, severity: (document.getElementById('dt-severity-' + i) || {}).value || t.severity, toxicity_action: (document.getElementById('dt-tox-' + i) || {}).value || t.toxicity_action, pii_action: (document.getElementById('dt-pii-' + i) || {}).value || t.pii_action }; });
  await post('/api/v1/settings/domain-thresholds', { thresholds: updated });
  showToast(t('domainSaved'), 'success');
}
async function renderBlocklist() {
  var bl = await get('/api/v1/settings/blocklist');
  var words = bl ? (bl.words || []) : [];
  var html = '<div class="card"><h2>' + t('customBlocklist') + '</h2><p class="dim mb">' + t('blocklistDesc') + '</p>';
  html += '<div style="display:flex;gap:8px;margin-bottom:16px"><input id="blocklist-word" class="form-input" placeholder="' + escapeHtml(t('blocklistPlaceholder')) + '" onkeydown="if(event.key===\'Enter\')addBlocklistWord()"/><button class="btn-primary" onclick="addBlocklistWord()" style="width:auto;padding:10px 20px;margin-top:0">' + t('addWord') + '</button></div>';
  html += '<table><thead><tr><th>Word</th><th>Action</th></tr></thead><tbody>';
  words.forEach(function (w) { html += '<tr><td>' + escapeHtml(w) + '</td><td><button class="filter-btn" onclick="removeBlocklistWord(\'' + escapeHtml(w) + '\')">' + t('remove') + '</button></td></tr>'; });
  if (!words.length) html += '<tr><td colspan="2" class="dim">' + t('noBlockedWords') + '</td></tr>';
  html += '</tbody></table></div>';
  document.getElementById('main-content').innerHTML = html;
}
async function addBlocklistWord() {
  var word = document.getElementById('blocklist-word').value.trim();
  if (!word) return;
  var result = await post('/api/v1/settings/blocklist', { word: word });
  if (result) { document.getElementById('blocklist-word').value = ''; renderBlocklist(); showToast(t('wordAdded'), 'success'); }
}
async function removeBlocklistWord(word) { await del('/api/v1/settings/blocklist/' + encodeURIComponent(word)); renderBlocklist(); showToast(t('wordRemoved'), 'success'); }
async function renderAuditLogs() {
  var logs = await get('/api/v1/audit?limit=50');
  var html = '<div class="card"><h2>' + t('auditLogs') + '</h2><p class="dim mb">' + t('auditDesc') + '</p>';
  html += '<table><thead><tr><th>User</th><th>Action</th><th>Resource</th><th>' + t('time') + '</th></tr></thead><tbody>';
  (logs || []).forEach(function (l) { html += '<tr><td>' + escapeHtml(l.user_email || '') + '</td><td>' + escapeHtml(l.action) + '</td><td>' + escapeHtml(l.resource_type || '') + '</td><td class="dim-sm">' + escapeHtml(l.timestamp || '') + '</td></tr>'; });
  if (!(logs || []).length) html += '<tr><td colspan="4" class="dim">' + t('noAuditLogs') + '</td></tr>';
  html += '</tbody></table></div>';
  document.getElementById('main-content').innerHTML = html;
}
async function renderHallucination() {
  var det = await get('/api/v1/hallucination/detections?limit=20');
  var items = (det && det.detections) ? det.detections : [];
  var html = '<div class="card"><h2>' + t('hallucinationDetections') + '</h2><p class="dim mb">' + t('hallucinationDesc') + '</p>';
  html += '<table><thead><tr><th>ID</th><th>Score</th><th>Prompt</th><th>Corrected</th></tr></thead><tbody>';
  items.forEach(function (d) { html += '<tr><td class="mono-sm">' + escapeHtml(d.id) + '</td><td>' + (d.score || 0).toFixed(2) + '</td><td class="text-snippet">' + escapeHtml((d.prompt_snippet || '').slice(0, 80)) + '...</td><td>' + (d.corrected ? buildBadge('clean', t('yes')) : buildBadge('toxic', t('no'))) + '</td></tr>'; });
  if (!items.length) html += '<tr><td colspan="4" class="dim">' + t('noHallucinations') + '</td></tr>';
  html += '</tbody></table></div>';
  document.getElementById('main-content').innerHTML = html;
}

// ── Canary Tokens ─────────────────────────────────────────────────
async function renderCanary() {
  var tokens = await get('/api/v1/canary/tokens');
  var alerts = await get('/api/v1/canary/alerts');
  var items = tokens || [];
  var alertItems = alerts || [];
  var activeCount = items.filter(function (t) { return t.status === 'active'; }).length;
  var html = '<div class="card"><h2>' + t('canaryTokens') + '</h2><p class="dim mb">' + t('canaryTokensDesc') + '</p>';
  html += '<div class="summary-grid">';
  html += '<div class="summary-card"><div class="label">' + t('activeTokens') + '</div><div class="value" style="color:#4F8EF7">' + activeCount + '</div></div>';
  html += '<div class="summary-card"><div class="label">' + t('canaryAlerts') + '</div><div class="value" style="color:' + (alertItems.length > 0 ? '#ef4444' : '#4F8EF7') + '">' + alertItems.length + '</div></div></div>';
  html += '<div class="card" style="margin-top:16px;border:1px solid rgba(79,142,247,0.2)"><h3>' + t('createCanary') + '</h3>';
  html += '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:12px">';
  html += '<input id="canary-label" class="form-input" placeholder="' + escapeHtml(t('canaryLabelPlaceholder')) + '" style="flex:1;min-width:200px"/>';
  html += '<input id="canary-prefix" class="form-input" placeholder="' + t('canaryPrefix') + '" value="pg" style="width:120px"/>';
  html += '<select id="canary-placement" class="form-select" style="width:160px">';
  html += '<option value="system_prompt">' + t('placementSystemPrompt') + '</option><option value="rag_store">' + t('placementRagStore') + '</option><option value="webhook">' + t('placementWebhook') + '</option></select>';
  html += '<button class="btn-primary" onclick="createCanaryToken()" style="width:auto;padding:10px 20px;margin-top:0">' + t('createCanary') + '</button></div>';
  html += '<div id="canary-created-display" style="margin-top:12px"></div></div>';
  html += '<div class="card" style="margin-top:16px"><h3>' + t('activeTokens') + '</h3><table><thead><tr><th>' + t('canaryLabel') + '</th><th>' + t('placement') + '</th><th>' + t('alertCount') + '</th><th>' + t('status') + '</th><th>Action</th></tr></thead><tbody>';
  items.forEach(function (t) {
    html += '<tr><td>' + escapeHtml(t.label) + '</td><td>' + escapeHtml(t.placement) + '</td><td>' + (t.alert_count || 0) + '</td><td>' + (t.status === 'active' ? buildBadge('clean', t('active')) : buildBadge('pii', t('revoked'))) + '</td>';
    html += '<td>' + (t.status === 'active' ? '<button class="filter-btn" onclick="revokeCanaryToken(\'' + escapeHtml(t.id) + '\')">' + t('revoke') + '</button>' : '<span class="dim-sm">-</span>') + '</td></tr>';
  });
  if (!items.length) html += '<tr><td colspan="5" class="dim">' + t('noCanaryTokens') + '</td></tr>';
  html += '</tbody></table></div>';
  html += '<div class="card" style="margin-top:16px"><h3>' + t('canaryAlerts') + '</h3><table><thead><tr><th>' + t('canaryLabel') + '</th><th>' + t('time') + '</th><th>' + t('sourceEndpoint') + '</th><th>' + t('sourceText') + '</th></tr></thead><tbody>';
  alertItems.forEach(function (a) { html += '<tr><td>' + escapeHtml(a.token_label || '') + '</td><td class="dim-sm">' + escapeHtml(a.detected_at || '') + '</td><td>' + escapeHtml(a.source_endpoint || '-') + '</td><td class="text-snippet">' + escapeHtml((a.source_text || '').slice(0, 60)) + '...</td></tr>'; });
  if (!alertItems.length) html += '<tr><td colspan="4" class="dim">' + t('noCanaryAlerts') + '</td></tr>';
  html += '</tbody></table></div>';
  document.getElementById('main-content').innerHTML = html;
}
async function createCanaryToken() {
  var label = document.getElementById('canary-label').value.trim();
  var prefix = document.getElementById('canary-prefix').value.trim() || 'pg';
  var placement = document.getElementById('canary-placement').value || 'system_prompt';
  if (!label) { showToast('Label is required', 'error'); return; }
  var result = await post('/api/v1/canary/tokens', { label: label, token_prefix: prefix, placement: placement });
  if (result) { document.getElementById('canary-created-display').innerHTML = '<div class="card" style="border:1px solid #22c55e"><h3 style="color:#22c55e">' + t('canaryCreated') + '</h3><div class="redacted-box">' + escapeHtml(result.token_hash) + '</div></div>'; document.getElementById('canary-label').value = ''; renderCanary(); showToast(t('canaryCreated'), 'success'); }
}
async function revokeCanaryToken(id) { if (!confirm(t('revoke') + ' token ' + id + '?')) return; await del('/api/v1/canary/tokens/' + id); renderCanary(); showToast(t('canaryRevoked'), 'success'); }

// ── Settings / API Keys / Webhooks / Users ────────────────────────
async function renderSettings() {
  var settings = await get('/api/v1/settings');
  var html = '<div class="card"><h2>' + t('settings') + '</h2>';
  html += '<div class="form-group"><label>' + t('email') + '</label><input id="settings-email" class="form-input" value="' + escapeHtml((settings && settings.admin_email) || '') + '"/></div>';
  html += '<div class="form-group"><label>' + (lang === 'fr' ? 'Mot de Passe Actuel' : 'Current Password') + '</label><input type="password" id="settings-curr-pw" class="form-input" placeholder="' + t('settingsReq') + '"/></div>';
  html += '<div class="form-group"><label>' + (lang === 'fr' ? 'Nouveau Mot de Passe' : 'New Password') + '</label><input type="password" id="settings-new-pw" class="form-input" placeholder="' + t('leaveBlank') + '"/></div>';
  html += '<hr style="border-color:rgba(79,142,247,0.1);margin:24px 0"/>';
  html += '<h3>Security</h3>';
  html += '<div class="form-group"><label>Session Timeout (idle minutes before auto-logout)</label>';
  html += '<select id="settings-timeout" class="form-select">';
  var timeout = (settings && settings.session_timeout_minutes) || 30;
  [15, 30, 60, 120, 240, 0].forEach(function(v) {
    html += '<option value="' + v + '"' + (timeout === v ? ' selected' : '') + '>' + (v === 0 ? 'Never' : v + ' minutes') + '</option>';
  });
  html += '</select></div>';
  html += '<hr style="border-color:rgba(79,142,247,0.1);margin:24px 0"/><h3>Language / Langue</h3><div style="display:flex;gap:8px;margin-top:12px">';
  html += '<button class="filter-btn' + (lang === 'en' ? ' active' : '') + '" onclick="setLang(\'en\')" style="font-size:16px">English</button>';
  html += '<button class="filter-btn' + (lang === 'fr' ? ' active' : '') + '" onclick="setLang(\'fr\')" style="font-size:16px">Français</button>';
  html += '<button class="filter-btn' + (lang === 'ar' ? ' active' : '') + '" onclick="setLang(\'ar\')" style="font-size:16px">العربية</button></div>';
  html += '<button class="btn-primary" onclick="saveAccountSettings()" style="width:auto;padding:10px 24px;margin-top:16px">' + t('saveSettings') + '</button></div>';
  document.getElementById('main-content').innerHTML = html;
}
async function saveAccountSettings() {
  var body = { admin_email: document.getElementById('settings-email').value };
  var cp = document.getElementById('settings-curr-pw').value, np = document.getElementById('settings-new-pw').value;
  var timeoutEl = document.getElementById('settings-timeout'); if (timeoutEl) { body.session_timeout_minutes = parseInt(timeoutEl.value); }
  if (cp && np) { body.current_password = cp; body.new_password = np; }
  await post('/api/v1/settings', body); showToast(t('settingsSaved'), 'success');
}
async function renderApiKeys() {
  var keys = await get('/api/v1/api-keys');
  var items = keys || [];
  var html = '<div class="card"><h2>' + t('apiKeys') + '</h2><p class="dim mb">Create API keys for programmatic access to PolarisGate.</p>';
  html += '<button class="btn-primary" onclick="createApiKey()" style="width:auto;padding:8px 20px;margin-bottom:16px">' + t('createNewKey') + '</button><div id="new-key-display"></div>';
  html += '<table><thead><tr><th>Key ID</th><th>Name</th><th>Scope</th><th>Created</th><th>Action</th></tr></thead><tbody>';
  items.forEach(function (k) { html += '<tr><td class="mono-sm">' + escapeHtml(k.key_id) + '</td><td>' + escapeHtml(k.name) + '</td><td class="dim-sm">' + escapeHtml(k.created_at || '') + '</td><td><button class="filter-btn" onclick="revokeApiKey(\'' + escapeHtml(k.key_id) + '\')">Revoke</button></td></tr>'; });
  if (!items.length) html += '<tr><td colspan="4" class="dim">' + t('noApiKeys') + '</td></tr>';
  html += '</tbody></table></div>'; document.getElementById('main-content').innerHTML = html;
}
async function createApiKey() {
  var name = document.getElementById("apikey-name").value.trim();
  var scope = document.getElementById("apikey-scope").value || "admin";
  if (!name) { name = "API Key"; }
  var result = await post('/api/v1/api-keys', { name: name, scope: scope });
  if (result) { document.getElementById('new-key-display').innerHTML = '<div class="card" style="margin-bottom:16px;border:1px solid #22c55e"><h3 style="color:#22c55e">' + t('keyCreated') + '</h3><p style="font-size:12px;color:#f59e0b;margin:8px 0">' + t('keyWarning') + '</p><div class="redacted-box">' + escapeHtml(result.api_key) + '</div></div>'; renderApiKeys(); }
}
async function revokeApiKey(keyId) { if (!confirm('Revoke key ' + keyId + '?')) return; await del('/api/v1/api-keys/' + keyId); renderApiKeys(); showToast(t('keyRevoked'), 'success'); }
async function renderWebhooks() {
  var wh = await get('/api/v1/settings/webhooks');
  var w = wh || { url: '', enabled: false, events: 'toxicity,pii' };
  var html = '<div class="card"><h2>' + t('webhookSettings') + '</h2><p class="dim mb">' + t('webhookDesc') + '</p>';
  html += '<div class="form-group"><label>' + t('webhookUrl') + '</label><input id="wh-url" class="form-input" value="' + escapeHtml(w.url || '') + '" placeholder="https://hooks.slack.com/services/..."/></div>';
  html += '<div class="form-group"><label>' + t('events') + '</label><input id="wh-events" class="form-input" value="' + escapeHtml(w.events || 'toxicity,pii') + '" placeholder="toxicity,pii"/></div>';
  html += '<div class="form-group"><label class="label-block">' + t('status') + '</label><label class="toggle"><input type="checkbox" id="wh-enabled"' + (w.enabled ? ' checked' : '') + '><span class="toggle-slider"></span></label> <span class="dim inline-label">' + (w.enabled ? t('active') : t('inactive')) + '</span></div>';
  html += '<button class="btn-primary" onclick="saveWebhook()" style="width:auto;padding:10px 24px">' + t('saveWebhook') + '</button></div>';
  document.getElementById('main-content').innerHTML = html;
}
async function saveWebhook() { await post('/api/v1/settings/webhooks', { url: document.getElementById('wh-url').value, enabled: document.getElementById('wh-enabled').checked, events: document.getElementById('wh-events').value }); showToast(t('webhookSaved'), 'success'); }
async function renderUsers() {
  var users = await get('/api/v1/users');
  var items = users || [];
  var html = '<div class="card"><h2>' + t('userManagement') + '</h2><p class="dim mb">' + t('userDesc') + '</p><div class="user-form">';
  html += '<input id="new-user-email" class="form-input" placeholder="' + escapeHtml(t('userEmailPlaceholder')) + '" onkeydown="if(event.key===\'Enter\')addUser()"/>';
  html += '<input id="new-user-pw" type="password" class="form-input" placeholder="' + t('passwordPlaceholder') + '"/>';
  html += '<select id="new-user-role" class="form-select"><option value="safety_officer">' + t('safetyOfficer') + '</option><option value="admin">' + t('admin') + '</option><option value="viewer">' + t('viewer') + '</option></select>';
  html += '<button class="btn-primary" onclick="addUser()" style="width:auto;padding:10px 20px;margin-top:0">' + t('createUser') + '</button></div>';
  html += '<table><thead><tr><th>' + t('email') + '</th><th>' + t('role') + '</th><th>' + t('status') + '</th><th>Action</th></tr></thead><tbody>';
  items.forEach(function (u) { html += '<tr><td>' + escapeHtml(u.email) + '</td><td>' + escapeHtml(u.role) + '</td><td>' + (u.active ? buildBadge('clean', t('active')) : buildBadge('toxic', t('inactive'))) + '</td><td>' + (u.active ? '<button class="filter-btn" onclick="deactivateUser(\'' + escapeHtml(u.email) + '\')">' + t('deactivate') + '</button>' : '<span class="dim-sm">' + t('inactive') + '</span>') + '</td></tr>'; });
  if (!items.length) html += '<tr><td colspan="4" class="dim">No users created</td></tr>';
  html += '</tbody></table></div>'; document.getElementById('main-content').innerHTML = html;
}
async function addUser() {
  var email = document.getElementById('new-user-email').value.trim();
  var pw = document.getElementById('new-user-pw').value, role = document.getElementById('new-user-role').value;
  if (!email || !pw) { showToast(t('emailPwRequired'), 'error'); return; }
  var result = await post('/api/v1/users', { email: email, password: pw, role: role });
  if (result) { renderUsers(); showToast(t('userCreated'), 'success'); }
}
async function deactivateUser(email) { if (!confirm('Deactivate ' + email + '?')) return; await del('/api/v1/users/' + encodeURIComponent(email)); renderUsers(); showToast(t('userDeactivated'), 'success'); }

// ── Init ──────────────────────────────────────────────────────────
(function init() {
  applyStaticI18n();
  token = localStorage.getItem('polarisgate-token');
  if (token) {
    document.getElementById('login-screen').classList.add('hidden');
    document.getElementById('dashboard-screen').classList.remove('hidden');
    render();
  }
})();