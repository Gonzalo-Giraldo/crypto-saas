(function () {
  const state = {
    sessionActive: false,
    role: null,
    broker: null,
  };

  function getSession() {
    return { ...state };
  }

  function setSession(next) {
    state.sessionActive = Boolean(next.sessionActive);
    state.role = next.role || null;
    state.broker = next.broker || null;

    if (window.ControlCenterEventBus) {
      window.ControlCenterEventBus.publish('session:changed', getSession());
    }
  }

  function clearSession() {
    setSession({
      sessionActive: false,
      role: null,
      broker: null,
    });
  }

  window.SessionStore = {
    getSession,
    setSession,
    clearSession,
  };
})();
