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

  function getAutopick(payload) {
    return payload && payload.autopick ? payload.autopick : {};
  }

  function present(status) {
    const payload = status && status.payload ? status.payload : {};
    const runtime = getRuntime(payload);
    const autopick = getAutopick(payload);

    const schedulerEnabled = typeof runtime.scheduler_enabled === 'boolean'
      ? runtime.scheduler_enabled
      : null;

    const tradingEnabled = typeof runtime.trading_enabled === 'boolean'
      ? runtime.trading_enabled
      : null;

    const overlapBlocked = Boolean(autopick.overlap_blocked);
    const runtimeLocked = Boolean(autopick.runtime_locked);
    const lastTickStatus = autopick.last_tick_status || 'UNKNOWN';
    const schedulerStale = Boolean(autopick.scheduler_stale);
    const operatorAttentionRequired = Boolean(autopick.operator_attention_required);

    return {
      loading: Boolean(status && status.loading),
      error: status ? status.error : null,
      schedulerState: schedulerEnabled === true ? 'ENABLED' : schedulerEnabled === false ? 'DISABLED' : 'UNKNOWN',
      tradingState: tradingEnabled === true ? 'ENABLED' : tradingEnabled === false ? 'DISABLED' : 'UNKNOWN',
      dryRun: autopick.dry_run === true ? 'DRY-RUN' : autopick.dry_run === false ? 'LIVE' : 'UNKNOWN',
      interval: runtime.scheduler_interval_minutes ? `${runtime.scheduler_interval_minutes} min` : 'UNKNOWN',
      lastTickStatus,
      lastTickAt: autopick.last_tick_at || 'NO TICK RECORDED',
      duration: autopick.last_tick_duration_ms === null || autopick.last_tick_duration_ms === undefined
        ? 'UNKNOWN'
        : `${autopick.last_tick_duration_ms} ms`,
      staleState: schedulerStale ? `STALE: ${autopick.stale_reason || 'unknown'}` : 'fresh',
      staleDuration: autopick.stale_duration_seconds === null || autopick.stale_duration_seconds === undefined
        ? 'unknown'
        : `${autopick.stale_duration_seconds}s`,
      lockState: overlapBlocked || runtimeLocked || schedulerStale || operatorAttentionRequired ? 'ATTENTION' : 'CLEAR',
      candidate: autopick.last_candidate_symbol || 'NONE',
      score: autopick.last_candidate_score || 'N/A',
      executionMode: autopick.last_execution_mode || 'UNKNOWN',
      lastError: autopick.last_error || 'none',
      rawText: status && status.error ? status.error : formatJson(payload),
      isError: Boolean(status && status.error) || lastTickStatus === 'ERROR' || overlapBlocked || runtimeLocked || schedulerStale || operatorAttentionRequired
    };
  }

  window.AutopickStatusPresenter = {
    present
  };
})();
