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

  function getSchedulerLifecycle(payload) {
    return payload && payload.scheduler_lifecycle ? payload.scheduler_lifecycle : {};
  }

  function getLatestJournalRow(payload) {
    const journal = payload && Array.isArray(payload.scheduler_tick_journal)
      ? payload.scheduler_tick_journal
      : [];
    return journal.length > 0 ? journal[0] : {};
  }

  function getObservationPayload(payload) {
    const latestJournal = getLatestJournalRow(payload);
    return latestJournal && latestJournal.observation_payload
      ? latestJournal.observation_payload
      : {};
  }

  function valueOrFallback(value, fallback) {
    return value === null || value === undefined || value === '' ? fallback : value;
  }

  function featureValue(candidate, key) {
    const features = candidate && candidate.features ? candidate.features : {};
    const value = features[key];
    return value === null || value === undefined ? 'N/A' : value;
  }

  function formatAverageScore(candidates) {
    const scores = candidates
      .map((candidate) => candidate.final_score === null || candidate.final_score === undefined ? NaN : Number(candidate.final_score))
      .filter((score) => Number.isFinite(score));

    if (scores.length === 0) {
      return 'N/A';
    }

    const average = scores.reduce((sum, score) => sum + score, 0) / scores.length;
    return average.toFixed(4);
  }

  function buildCandidateReason(candidate) {
    const features = candidate && candidate.features ? candidate.features : {};
    const parts = [];

    if (candidate && candidate.reason) {
      parts.push(`reason=${candidate.reason}`);
    }

    ['spread_bps', 'atr_risk', 'volume_relative', 'liquidity_factor', 'confirmation_score'].forEach((key) => {
      if (features[key] !== null && features[key] !== undefined) {
        parts.push(`${key}=${features[key]}`);
      }
    });

    return parts.length > 0 ? parts.join(' | ') : 'N/A';
  }

  function buildCandidateRows(payload) {
    const observation = getObservationPayload(payload);
    const candidates = Array.isArray(observation.candidates) ? observation.candidates : [];

    return candidates.map((candidate) => ({
      rank: valueOrFallback(candidate.rank, 'N/A'),
      symbol: valueOrFallback(candidate.symbol, 'UNKNOWN'),
      score: valueOrFallback(candidate.final_score, 'N/A'),
      spreadBps: featureValue(candidate, 'spread_bps'),
      atrRisk: featureValue(candidate, 'atr_risk'),
      volumeRelative: featureValue(candidate, 'volume_relative'),
      reason: buildCandidateReason(candidate),
      selected: Boolean(candidate.selected),
    }));
  }

  function buildObservationSummary(payload) {
    const latestJournal = getLatestJournalRow(payload);
    const observation = getObservationPayload(payload);
    const selected = observation.selected || {};

    return {
      decisionStatus: latestJournal.decision_status || observation.decision_status || 'UNKNOWN',
      selectedRank: valueOrFallback(latestJournal.selected_rank || observation.selected_rank, 'N/A'),
      rankedCount: valueOrFallback(latestJournal.ranked_count || observation.ranked_count, 'N/A'),
      topN: valueOrFallback(latestJournal.top_n || observation.top_n, 'N/A'),
      selectedSymbol: valueOrFallback(observation.selected_symbol || selected.symbol, 'NONE'),
      selectedScore: valueOrFallback(selected.final_score || latestJournal.candidate_score, 'N/A'),
    };
  }

  function buildTraceRows(payload, autopick, runtime, lifecycle) {
    const latestJournal = getLatestJournalRow(payload);
    const effectiveState = lifecycle.effective_state || 'UNKNOWN';
    const desiredState = lifecycle.desired_state || 'UNKNOWN';
    const tickStatus = autopick.last_tick_status || latestJournal.status || 'UNKNOWN';
    const staleReason = autopick.scheduler_stale ? (autopick.stale_reason || 'unknown') : 'fresh';
    const candidate = autopick.last_candidate_symbol || latestJournal.candidate_symbol || 'NONE';
    const score = autopick.last_candidate_score || latestJournal.candidate_score || 'N/A';
    const executionMode = autopick.last_execution_mode || latestJournal.execution_mode || 'UNKNOWN';

    return [
      {
        label: '1. DATA observation',
        value: effectiveState,
        detail: `desired=${desiredState} | enabled=${runtime.scheduler_enabled === true ? 'yes' : runtime.scheduler_enabled === false ? 'no' : 'unknown'}`
      },
      {
        label: '2. Market-data tick',
        value: tickStatus,
        detail: `last_tick_at=${autopick.last_tick_at || latestJournal.started_at || 'none'} | stale=${staleReason}`
      },
      {
        label: '3. Runtime lock',
        value: autopick.runtime_locked || autopick.overlap_blocked ? 'ATTENTION' : 'CLEAR',
        detail: `runtime_locked=${Boolean(autopick.runtime_locked)} | overlap_blocked=${Boolean(autopick.overlap_blocked)}`
      },
      {
        label: '4. Top observed candidate',
        value: candidate,
        detail: `score=${score} | mode=${executionMode}`
      },
      {
        label: '5. Mutation posture',
        value: latestJournal.mutation_executed ? 'MUTATED' : latestJournal.mutation_attempted ? 'ATTEMPTED' : 'READ-ONLY',
        detail: `attempted=${Boolean(latestJournal.mutation_attempted)} | executed=${Boolean(latestJournal.mutation_executed)}`
      }
    ];
  }

  function present(status) {
    const payload = status && status.payload ? status.payload : {};
    const runtime = getRuntime(payload);
    const autopick = getAutopick(payload);
    const lifecycle = getSchedulerLifecycle(payload);

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
      schedulerLifecycle: lifecycle.effective_state || 'UNKNOWN',
      traceRows: buildTraceRows(payload, autopick, runtime, lifecycle),
      observationSummary: buildObservationSummary(payload),
      candidateRows: buildCandidateRows(payload),
      averageScore: formatAverageScore((getObservationPayload(payload).candidates || [])),
      rawText: status && status.error ? status.error : formatJson(payload),
      isError: Boolean(status && status.error) || lastTickStatus === 'ERROR' || overlapBlocked || runtimeLocked || schedulerStale || operatorAttentionRequired
    };
  }

  window.AutopickStatusPresenter = {
    present
  };
})();
