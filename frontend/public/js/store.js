/** PolarisGate v3.0 — State Store */
var store = (function () {
  var _state = { tab: 'dashboard', sub: 'overview', _filter: null, teamId: 'default', budgets: [], agents: [] };
  return {
    get: function (key) { return _state[key]; },
    set: function (key, value) { _state[key] = value; },
    getAll: function () { return _state; },
    update: function (partial) {
      Object.keys(partial).forEach(function (k) { _state[k] = partial[k]; });
      if (typeof render === 'function') render();
    },
    navigate: function (tab, sub) {
      _state.tab = tab;
      _state.sub = sub || 'overview';
      if (tab !== 'dashboard' || sub !== 'incidents') _state._filter = null;
      if (typeof _incidentCache !== 'undefined') _incidentCache = {};
      if (typeof render === 'function') render();
    }
  };
})();