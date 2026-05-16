(function () {
  function formatJson(value) {
    try {
      return JSON.stringify(value, null, 2);
    } catch (_error) {
      return String(value);
    }
  }

  function getRuntime(payload) {
    return payload && payload.runtime ? payload.runtime : {};
  }

  function getProtections(payload) {
    return payload && payload.protections ? payload.protections : {};
  }

  function getTradingState(payload) {
    const runtime = getRuntime(payload);

    if (typeof runtime.trading_enabled !== 'boolean') {
      return 'UNKNOWN';
    }

    return runtime.trading_enabled ? 'ENABLED' : 'DISABLED';
  }

  function getSchedulerState(payload) {
    const runtime = getRuntime(payload);

    if (typeof runtime.scheduler_enabled !== 'boolean') {
      return 'UNKNOWN';
    }

    return runtime.scheduler_enabled ? 'ENABLED' : 'DISABLED';
  }

  function present(runtimeStatus) {
    const payload = runtimeStatus && runtimeStatus.payload ? runtimeStatus.payload : {};
    const tradingState = getTradingState(payload);
    const schedulerState = getSchedulerState(payload);
    const runtime = getRuntime(payload);
    const protections = getProtections(payload);
    const unknownCount = Number(protections.unknown_positions || 0);
    const pendingCleanupCount = Number(protections.pending_cleanup_positions || 0);

    return {
      loading: Boolean(runtimeStatus && runtimeStatus.loading),
      error: runtimeStatus ? runtimeStatus.error : null,
      tradingState,
      tradingDetail:
        tradingState === 'ENABLED'
          ? 'Runtime mutations may be allowed by backend gates.'
          : tradingState === 'DISABLED'
            ? 'Global kill-switch is blocking trading mutations.'
            : 'Trading state unavailable; treat as fail-closed.',
      schedulerState,
      schedulerDetail:
        schedulerState === 'ENABLED'
          ? 'Scheduler is configured as enabled.'
          : schedulerState === 'DISABLED'
            ? 'Scheduler is not configured as enabled.'
            : 'Scheduler state unavailable from current endpoint.',
      environment: runtime.environment || runtime.branch || 'UNKNOWN',
      environmentDetail: `Commit: ${runtime.commit || 'unknown'}`,
      protectionAlerts: unknownCount > 0 || pendingCleanupCount > 0 ? 'ATTENTION' : 'CLEAR',
      protectionDetail: `UNKNOWN: ${unknownCount} | Pending cleanup: ${pendingCleanupCount} | Active protected: ${protections.active_protected_positions || 0}`,
      rawText: runtimeStatus && runtimeStatus.error
        ? runtimeStatus.error
        : formatJson(payload),
      isError: Boolean(runtimeStatus && runtimeStatus.error)
    };
  }

  window.RuntimeStatusPresenter = {
    present
  };
})();
