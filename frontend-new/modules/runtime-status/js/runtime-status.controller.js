(function () {
  let unsubscribeRefresh = null;

  async function refreshRuntimeStatus() {
    if (!window.ControlCenterStore || !window.RuntimeStatusService) {
      return;
    }

    window.ControlCenterStore.setRuntimeStatus({
      loading: true,
      error: null
    });

    try {
      const result = await window.RuntimeStatusService.fetchRuntimeStatus();

      if (!result.ok) {
        window.ControlCenterStore.setRuntimeStatus({
          loading: false,
          error: result.rawBody || `Runtime status failed: ${result.status}`,
          payload: result.payload,
          updatedAt: new Date().toISOString()
        });
        return;
      }

      window.ControlCenterStore.setRuntimeStatus({
        loading: false,
        error: null,
        payload: result.payload,
        updatedAt: new Date().toISOString()
      });
    } catch (error) {
      window.ControlCenterStore.setRuntimeStatus({
        loading: false,
        error: error && error.message ? error.message : 'Unknown runtime status error.',
        updatedAt: new Date().toISOString()
      });
    }
  }

  function start() {
    if (!window.ControlCenterEventBus) {
      return;
    }

    if (typeof unsubscribeRefresh === 'function') {
      return;
    }

    unsubscribeRefresh = window.ControlCenterEventBus.subscribe(
      'runtime-status:refresh-requested',
      refreshRuntimeStatus
    );
  }

  function stop() {
    if (typeof unsubscribeRefresh === 'function') {
      unsubscribeRefresh();
      unsubscribeRefresh = null;
    }
  }

  window.RuntimeStatusController = {
    start,
    stop,
    refreshRuntimeStatus
  };
})();
