(function () {
  let unsubscribeRefresh = null;

  async function refreshAutopickStatus() {
    if (!window.ControlCenterStore || !window.AutopickStatusService) {
      return;
    }

    window.ControlCenterStore.setAutopickStatus({
      loading: true,
      error: null
    });

    try {
      const result = await window.AutopickStatusService.fetchAutopickStatus();

      if (!result.ok) {
        window.ControlCenterStore.setAutopickStatus({
          loading: false,
          error: result.rawBody || `Autopick status failed: ${result.status}`,
          payload: result.payload,
          updatedAt: new Date().toISOString()
        });
        return;
      }

      window.ControlCenterStore.setAutopickStatus({
        loading: false,
        error: null,
        payload: result.payload,
        updatedAt: new Date().toISOString()
      });
    } catch (error) {
      window.ControlCenterStore.setAutopickStatus({
        loading: false,
        error: error && error.message ? error.message : 'Unknown autopick status error.',
        updatedAt: new Date().toISOString()
      });
    }
  }

  function start() {
    if (!window.ControlCenterEventBus || typeof unsubscribeRefresh === 'function') {
      return;
    }

    unsubscribeRefresh = window.ControlCenterEventBus.subscribe(
      'autopick-status:refresh-requested',
      refreshAutopickStatus
    );
  }

  function stop() {
    if (typeof unsubscribeRefresh === 'function') {
      unsubscribeRefresh();
      unsubscribeRefresh = null;
    }
  }

  window.AutopickStatusController = {
    start,
    stop,
    refreshAutopickStatus
  };
})();
