(function () {
  const state = {
    runtimeStatus: {
      loading: false,
      error: null,
      payload: null,
      updatedAt: null
    },
    autopickStatus: {
      loading: false,
      error: null,
      payload: null,
      updatedAt: null
    }
  };

  function getState() {
    return JSON.parse(JSON.stringify(state));
  }

  function setRuntimeStatus(nextRuntimeStatus) {
    state.runtimeStatus = {
      ...state.runtimeStatus,
      ...nextRuntimeStatus
    };

    if (window.ControlCenterEventBus) {
      window.ControlCenterEventBus.publish('store:runtime-status:changed', getState().runtimeStatus);
    }
  }

  function setAutopickStatus(nextAutopickStatus) {
    state.autopickStatus = {
      ...state.autopickStatus,
      ...nextAutopickStatus
    };

    if (window.ControlCenterEventBus) {
      window.ControlCenterEventBus.publish('store:autopick-status:changed', getState().autopickStatus);
    }
  }

  window.ControlCenterStore = {
    getState,
    setRuntimeStatus,
    setAutopickStatus
  };
})();
