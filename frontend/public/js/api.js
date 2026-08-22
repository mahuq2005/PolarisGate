/** PolarisGate v3.0 — API Client (Centralized)
 *  All backend calls go through here. Auth header injection, error handling, retry.
 */
var api = (function () {
  // Relative path — nginx (frontend container or edge proxy) forwards /api/ to the gateway.
  var BASE = '';

  async function _fetch(method, endpoint, body) {
    var headers = { 'Content-Type': 'application/json' };
    if (typeof token !== 'undefined' && token) {
      headers['Authorization'] = 'Bearer ' + token;
    }
    var opts = { method: method, headers: headers };
    if (body) opts.body = JSON.stringify(body);
    try {
      var r = await fetch(BASE + endpoint, opts);
      if (!r.ok) {
        var j = await r.json().catch(function () { return {}; });
        throw new Error(j.detail || 'Request failed (' + r.status + ')');
      }
      return r.json();
    } catch (e) {
      if (typeof showToast !== 'undefined') showToast(e.message, 'error');
      return null;
    }
  }

  return {
    dashboard: {
      getSummary: function () { return _fetch('GET', '/api/v1/dashboard/summary'); },
      getIncidents: function (limit) { return _fetch('GET', '/api/v1/dashboard/incidents?limit=' + (limit || 30)); },
      getModels: function () { return _fetch('GET', '/api/v1/dashboard/models'); }
    },
    policy: {
      getPolicies: function () { return _fetch('GET', '/api/v1/policies'); },
      savePolicies: function (p) { return _fetch('POST', '/api/v1/policies', { policies: p }); },
      check: function (text) { return _fetch('POST', '/api/v1/guardrails/check', { text: text }); },
      checkBatch: function (texts) { return _fetch('POST', '/api/v1/guardrails/batch', { texts: texts }); },
      getThresholds: function () { return _fetch('GET', '/api/v1/settings/domain-thresholds'); },
      saveThresholds: function (t) { return _fetch('POST', '/api/v1/settings/domain-thresholds', { thresholds: t }); },
      getBlocklist: function () { return _fetch('GET', '/api/v1/settings/blocklist'); },
      addBlocklist: function (w) { return _fetch('POST', '/api/v1/settings/blocklist', { word: w }); },
      removeBlocklist: function (w) { return _fetch('DELETE', '/api/v1/settings/blocklist/' + encodeURIComponent(w)); }
    },
    cost: {
      getUsage: function (teamId, days) { return _fetch('GET', '/api/v1/cost/usage?team_id=' + (teamId || 'default') + '&days=' + (days || 30)); },
      getAnomaly: function (teamId) { return _fetch('GET', '/api/v1/cost/anomaly?team_id=' + (teamId || 'default')); },
      getBudgets: function () { return _fetch('GET', '/api/v1/cost/budgets'); },
      createBudget: function (b) { return _fetch('POST', '/api/v1/cost/budgets', b); },
      updateBudget: function (id, b) { return _fetch('PUT', '/api/v1/cost/budgets/' + id, b); },
      deleteBudget: function (id) { return _fetch('DELETE', '/api/v1/cost/budgets/' + id); }
    },
    agents: {
      getStatus: function () { return _fetch('GET', '/api/v1/agents/status'); },
      list: function () { return _fetch('GET', '/api/v1/agents'); },
      create: function (a) { return _fetch('POST', '/api/v1/agents', a); },
      remove: function (id) { return _fetch('DELETE', '/api/v1/agents/' + id); },
      start: function (id) { return _fetch('POST', '/api/v1/agents/' + id + '/start'); },
      stop: function (id) { return _fetch('POST', '/api/v1/agents/' + id + '/stop'); },
      listMcp: function () { return _fetch('GET', '/api/v1/agents/mcp'); },
      registerMcp: function (m) { return _fetch('POST', '/api/v1/agents/mcp', m); }
    },
    rag: {
      getStatus: function () { return _fetch('GET', '/api/v1/rag/status'); },
      getGraphStatus: function () { return _fetch('GET', '/api/v1/rag/graph/status'); },
      listDocs: function () { return _fetch('GET', '/api/v1/rag/documents'); },
      search: function (q) { return _fetch('POST', '/api/v1/rag/search', { query: q }); }
    },
    compliance: {
      getHallucinations: function (limit) { return _fetch('GET', '/api/v1/hallucination/detections?limit=' + (limit || 20)); },
      getHallucinationTrend: function () { return _fetch('GET', '/api/v1/hallucination/trend'); },
      getAuditLogs: function (limit) { return _fetch('GET', '/api/v1/audit?limit=' + (limit || 50)); },
      getAccuracyStatus: function () { return _fetch('GET', '/api/v1/accuracy/status'); },
      getRagasScores: function () { return _fetch('GET', '/api/v1/accuracy/ragas'); }
    },
    admin: {
      getSettings: function () { return _fetch('GET', '/api/v1/settings'); },
      saveSettings: function (s) { return _fetch('POST', '/api/v1/settings', s); },
      getApiKeys: function () { return _fetch('GET', '/api/v1/api-keys'); },
      createApiKey: function (k) { return _fetch('POST', '/api/v1/api-keys', k); },
      revokeApiKey: function (id) { return _fetch('DELETE', '/api/v1/api-keys/' + id); },
      getWebhooks: function () { return _fetch('GET', '/api/v1/settings/webhooks'); },
      saveWebhooks: function (w) { return _fetch('POST', '/api/v1/settings/webhooks', w); },
      getUsers: function () { return _fetch('GET', '/api/v1/users'); },
      createUser: function (u) { return _fetch('POST', '/api/v1/users', u); },
      deactivateUser: function (email) { return _fetch('DELETE', '/api/v1/users/' + encodeURIComponent(email)); },
      getCanaryTokens: function () { return _fetch('GET', '/api/v1/canary/tokens'); },
      getCanaryAlerts: function (limit) { return _fetch('GET', '/api/v1/canary/alerts?limit=' + (limit || 50)); },
      createCanary: function (c) { return _fetch('POST', '/api/v1/canary/tokens', c); },
      revokeCanary: function (id) { return _fetch('DELETE', '/api/v1/canary/tokens/' + id); }
    },
    chat: {
      getProviders: function () { return _fetch('GET', '/api/v1/chat/providers'); },
      sendMessage: function (provider, text) {
        return _fetch('POST', '/api/v1/chat/completions', { provider: provider, messages: [{ role: 'user', content: text }] });
      }
    }
  };
})();