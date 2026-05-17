(function () {
  let root = null;

  function destroyCurrentController() {
    if (
      window.AutopickStatusController &&
      typeof window.AutopickStatusController.unmount === 'function'
    ) {
      window.AutopickStatusController.unmount();
    }
  }

  function setText(selector, value) {
    const node = root ? root.querySelector(selector) : null;
    if (node) {
      node.textContent = value;
    }
  }

  function setOutput(value, isError) {
    const output = root ? root.querySelector('#autopick-status-output') : null;
    if (!output) {
      return;
    }

    output.textContent = value;
    output.classList.toggle('is-error', Boolean(isError));
  }

  function renderCandidateRows(rows) {
    const body = root ? root.querySelector('#autopick-candidate-ranking-body') : null;
    if (!body) {
      return;
    }

    body.textContent = '';

    const safeRows = Array.isArray(rows) ? rows : [];

    if (safeRows.length === 0) {
      const row = document.createElement('tr');
      const cell = document.createElement('td');
      cell.colSpan = 8;
      cell.textContent = 'No candidate ranking available.';
      row.appendChild(cell);
      body.appendChild(row);
      return;
    }

    safeRows.slice(0, 5).forEach((candidate) => {
      const row = document.createElement('tr');
      row.classList.toggle('is-selected', Boolean(candidate.selected));

      [
        candidate.rank,
        candidate.symbol,
        candidate.score,
        candidate.spreadBps,
        candidate.atrRisk,
        candidate.volumeRelative,
        candidate.reason,
        '→',
      ].forEach((value) => {
        const cell = document.createElement('td');
        cell.textContent = value === null || value === undefined ? 'N/A' : value;
        row.appendChild(cell);
      });

      body.appendChild(row);
    });
  }

  function renderTraceRows(rows) {
    const container = root ? root.querySelector('#autopick-trace-rows') : null;
    if (!container) {
      return;
    }

    container.textContent = '';

    const safeRows = Array.isArray(rows) ? rows : [];

    if (safeRows.length === 0) {
      container.textContent = 'No auto-pick trace available.';
      return;
    }

    safeRows.slice(0, 5).forEach((traceRow, index) => {
      const item = document.createElement('article');
      item.className = 'ap-trace-step';

      item.innerHTML = `
        <div class="ap-trace-number">${index + 1}</div>
        <div class="ap-trace-icon">${
          ['◷', '◎', '◌', '▤', '⌘'][index] || '•'
        }</div>
        <strong>${traceRow.label || 'Step'}</strong>
        <span class="ap-badge">${traceRow.value || 'UNKNOWN'}</span>
        <p>${traceRow.detail || ''}</p>
      `;

      container.appendChild(item);
    });
  }

  function getTemplate() {
    return `
      <section class="ap" aria-label="Auto-pick Status module">
        <header class="ap-header">
          <div>
            <h3>Auto-pick Status</h3>
            <p>Real-time auto-pick runtime status, observation summary, and candidate ranking.</p>
          </div>
          <button id="autopick-refresh-button" type="button" class="ap-refresh">⟳ Refresh Now</button>
        </header>

        <section class="ap-cards" aria-label="Auto-pick status cards">
          <article class="ap-card">
            <div class="ap-card-icon">◷</div>
            <div>
              <h4>Scheduler</h4>
              <p>Interval: <strong id="autopick-interval">UNKNOWN</strong></p>
              <p>Mode: <strong id="autopick-mode">UNKNOWN</strong></p>
              <p>Execution: <strong id="autopick-execution-mode">UNKNOWN</strong></p>
            </div>
          </article>

          <article class="ap-card">
            <div class="ap-card-icon">⌁</div>
            <div>
              <h4>Last Tick</h4>
              <p>Status: <strong id="autopick-last-tick-status">UNKNOWN</strong></p>
              <p>At: <strong id="autopick-last-tick-at">NO TICK RECORDED</strong></p>
            </div>
          </article>

          <article class="ap-card">
            <div class="ap-card-icon">▥</div>
            <div>
              <h4>Trading</h4>
              <p>State: <strong id="autopick-trading-state">UNKNOWN</strong></p>
              <p>Lock: <strong id="autopick-lock-state">UNKNOWN</strong></p>
              <p>Duration: <strong id="autopick-duration">UNKNOWN</strong></p>
            </div>
          </article>

          <article class="ap-card">
            <div class="ap-card-icon">◎</div>
            <div>
              <h4>Candidate</h4>
              <p>Symbol: <strong id="autopick-candidate">NONE</strong></p>
              <p>Score: <strong id="autopick-score">N/A</strong></p>
            </div>
          </article>
        </section>

        <section class="ap-panel">
          <h4>Observation Summary</h4>
          <div class="ap-summary">
            <div class="ap-summary-item">
              <span>Decision</span>
              <strong id="autopick-decision-status" class="ap-decision">UNKNOWN</strong>
            </div>
            <div class="ap-summary-item">
              <span>Selected Symbol</span>
              <strong id="autopick-selected-symbol">NONE</strong>
            </div>
            <div class="ap-summary-item">
              <span>Selected Rank</span>
              <strong id="autopick-selected-rank">N/A</strong>
            </div>
            <div class="ap-summary-item">
              <span>Ranked Count</span>
              <strong id="autopick-ranked-count">N/A</strong>
            </div>
            <div class="ap-summary-item">
              <span>Top N</span>
              <strong id="autopick-top-n">N/A</strong>
            </div>
            <div class="ap-summary-item">
              <span>Selected Score</span>
              <strong id="autopick-selected-score">N/A</strong>
            </div>
          </div>
        </section>

        <section class="ap-grid">
          <article class="ap-panel">
            <h4>Candidate Ranking (Top N)</h4>
            <div class="ap-average">
              <span>Score Promedio</span>
              <strong id="autopick-average-score">N/A</strong>
            </div>

            <table class="ap-table">
              <thead>
                <tr>
                  <th>Rank</th>
                  <th>Symbol</th>
                  <th>Score</th>
                  <th>Reason: Spread</th>
                  <th>Reason: ATR</th>
                  <th>Reason: Volume</th>
                  <th>Reason</th>
                  <th></th>
                </tr>
              </thead>
              <tbody id="autopick-candidate-ranking-body">
                <tr><td colspan="8">No candidate ranking loaded.</td></tr>
              </tbody>
            </table>

            <p class="ap-table-note">
              Scores observacionales. No muta Risk, Intent, Execution ni Auto-pick core.
            </p>
          </article>

          <article class="ap-panel">
            <h4>Trace (Last Decision Cycle)</h4>
            <section id="autopick-trace-rows" class="ap-trace">No auto-pick trace loaded.</section>
          </article>
        </section>

        <section class="ap-panel">
          <h4>Raw Output / Message</h4>
          <pre id="autopick-status-output" class="ap-output">No auto-pick status loaded.</pre>
        </section>
      </section>
    `;
  }

  function renderState(status) {
    if (!root || !window.AutopickStatusPresenter) {
      return;
    }

    const view = window.AutopickStatusPresenter.present(status);
    const observation = view.observationSummary || {};

    setText('#autopick-interval', view.interval);
    setText('#autopick-mode', view.dryRun);
    setText('#autopick-execution-mode', view.executionMode);
    setText('#autopick-last-tick-status', view.lastTickStatus);
    setText('#autopick-last-tick-at', view.lastTickAt);
    setText('#autopick-trading-state', view.tradingState);
    setText('#autopick-lock-state', view.lockState);
    setText('#autopick-duration', view.duration);
    setText('#autopick-candidate', view.candidate);
    setText('#autopick-score', view.score);

    setText('#autopick-decision-status', observation.decisionStatus || 'UNKNOWN');
    setText('#autopick-selected-symbol', observation.selectedSymbol || 'NONE');
    setText('#autopick-selected-rank', String(observation.selectedRank || 'N/A'));
    setText('#autopick-ranked-count', String(observation.rankedCount || 'N/A'));
    setText('#autopick-top-n', String(observation.topN || 'N/A'));
    setText('#autopick-selected-score', String(observation.selectedScore || 'N/A'));
    setText('#autopick-average-score', String(view.averageScore || 'N/A'));

    renderCandidateRows(view.candidateRows);
    renderTraceRows(view.traceRows);
    setOutput(view.loading ? 'Loading auto-pick status...' : view.rawText, view.isError);
  }

  function mount(target) {
    destroyCurrentController();
    root = target;

    if (!root) {
      return;
    }

    root.innerHTML = getTemplate();

    const refreshButton = root.querySelector('#autopick-refresh-button');
    if (refreshButton && window.ControlCenterEventBus) {
      refreshButton.addEventListener('click', () => {
        window.ControlCenterEventBus.publish('runtime:refresh');
      });
    }

    if (
      window.AutopickStatusController &&
      typeof window.AutopickStatusController.mount === 'function'
    ) {
      window.AutopickStatusController.mount(renderState);
    }
  }

  function unmount() {
    destroyCurrentController();
    root = null;
  }

  window.AutopickStatusModule = {
    id: 'autopick-status',
    title: 'Auto-pick Status',
    mount,
    unmount
  };
})();
