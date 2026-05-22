(function () {
  const POLL_INTERVAL_MS = 10000;

  let unsubscribeRefresh = null;
  let pollingHandle = null;

  async function refreshAutopickStatus() {
    if (!window.AutopickStatusService) {
      return {
        payload: null,
        error: 'Auto-pick status service unavailable.',
      };
    }

    return window.AutopickStatusService.fetchAutopickStatus();
  }

  async function loadStatus(render) {
    if (typeof render !== 'function') {
      return;
    }

    const status = await refreshAutopickStatus();

    render({
      loading: false,
      payload: status.payload || null,
      error: status.error || null,
    });
  }

  function stopPolling() {
    if (pollingHandle) {
      window.clearInterval(pollingHandle);
      pollingHandle = null;
    }
  }

  function startPolling(render) {
    stopPolling();

    pollingHandle = window.setInterval(() => {
      loadStatus(render);
    }, POLL_INTERVAL_MS);
  }

  function mount(render) {
    loadStatus(render);
    startPolling(render);

    if (
      window.ControlCenterEventBus &&
      typeof window.ControlCenterEventBus.subscribe === 'function'
    ) {
      unsubscribeRefresh = window.ControlCenterEventBus.subscribe(
        'runtime:refresh',
        () => {
          loadStatus(render);
        }
      );
    }
  }

  function unmount() {
    stopPolling();

    if (typeof unsubscribeRefresh === 'function') {
      unsubscribeRefresh();
      unsubscribeRefresh = null;
    }
  }

  window.AutopickStatusController = {
    mount,
    unmount,
  };
})();
