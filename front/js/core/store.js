(function () {
  const state = { auth: {auth_enabled: false, logged_in: false, role: null, username: null}, settings: {}, listeners: new Set() };
  function update(patch) { Object.assign(state, patch); state.listeners.forEach(listener => listener(state)); }
  function subscribe(listener) { state.listeners.add(listener); return () => state.listeners.delete(listener); }
  window.HamLogStore = { state, update, subscribe };
}());
