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

    safeRows.forEach((candidate) => {
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
        candidate.selected ? 'YES' : 'NO',
      ].forEach((value) => {
        const cell = document.createElement('td');
        cell.textContent = value;
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
      const empty = document.createElement('div');
      empty.className = 'autopick-trace-empty';
      empty.textContent = 'No auto-pick trace available.';
      container.appendChild(empty);
      return;
    }

    safeRows.forEach((row, index) => {
      const item = document.createElement('article');
      item.className = 'autopick-trace-step';

      const stepIndex = document.createElement('div');
      stepIndex.className = 'autopick-trace-index';
      stepIndex.textContent = String(index + 1);

      const component = document.createElement('div');
      component.className = 'autopick-trace-component';
      component.textContent = row.label || 'Step';

      const status = document.createElement('div');
      status.className = 'autopick-trace-status';
      status.textContent = row.value || 'UNKNOWN';

      const detail = document.createElement('div');
      detail.className = 'autopick-trace-detail';
      detail.textContent = row.detail || '';

      item.appendChild(stepIndex);
      item.appendChild(component);
      item.appendChild(status);
      item.appendChild(detail);

      container.appendChild(item);
    });
  }

  function getTemplate() {
    return `
      <section class="autopick-status" aria-label="Auto-pick Status module">
        <header class="autopick-header">
          <div>
            <h3>Auto-pick Status</h3>
            <p>Operational visibility for scheduler ticks, dry-run/live posture, overlap blocking, last candidate, and tick errors.</p>
          </div>
        </header>

        <section class="autopick-grid" aria-label="Auto-pick status cards">
          <article class="autopick-card">
            <span class="autopick-card-label">Scheduler</span>
            <strong id="autopick-scheduler-state">UNKNOWN</strong>
            <p id="autopick-interval">Interval unknown.</p>
          </article>

          <article class="autopick-card">
            <span class="autopick-card-label">Mode</span>
            <strong id="autopick-mode">UNKNOWN</strong>
            <p id="autopick-trading-state">Trading state unknown.</p>
          </article>

          <article class="autopick-card">
            <span class="autopick-card-label">Last Tick</span>
            <strong id="autopick-last-tick-status">UNKNOWN</strong>
            <p id="autopick-last-tick-at">No tick recorded.</p>
          </article>

          <article class="autopick-card">
            <span class="autopick-card-label">Runtime Lock</span>
            <strong id="autopick-lock-state">UNKNOWN</strong>
            <p id="autopick-duration">Duration unknown.</p>
          </article>

          <article class="autopick-card">
            <span class="autopick-card-label">Candidate</span>
            <strong id="autopick-candidate">NONE</strong>
            <p id="autopick-score">Score unavailable.</p>
          </article>

          <article class="autopick-card">
            <span class="autopick-card-label">Execution Mode</span>
            <strong id="autopick-execution-mode">UNKNOWN</strong>
            <p id="autopick-last-error">No error.</p>
          </article>
        </section>

        <section class="autopick-panel" aria-label="Auto-pick observation summary">
          <div class="autopick-panel-header">
            <div>
              <span class="autopick-card-label">Observation Summary</span>
              <h4>Selection Contract</h4>
            </div>
          </div>

          <section class="autopick-observation-summary">
            <article class="autopick-mini-card">
              <span>Decision</span>
              <strong id="autopick-decision-status">UNKNOWN</strong>
            </article>
            <article class="autopick-mini-card">
              <span>Selected Symbol</span>
              <strong id="autopick-selected-symbol">NONE</strong>
            </article>
            <article class="autopick-mini-card">
              <span>Selected Rank</span>
              <strong id="autopick-selected-rank">N/A</strong>
            </article>
            <article class="autopick-mini-card">
              <span>Ranked Count</span>
              <strong id="autopick-ranked-count">N/A</strong>
            </article>
            <article class="autopick-mini-card">
              <span>Top N</span>
              <strong id="autopick-top-n">N/A</strong>
            </article>
            <article class="autopick-mini-card">
              <span>Selected Score</span>
              <strong id="autopick-selected-score">N/A</strong>
            </article>
          </section>
        </section>

        <section class="autopick-panel" aria-label="Auto-pick candidate ranking">
          <div class="autopick-panel-header">
            <div>
              <span class="autopick-card-label">Candidate Ranking</span>
              <h4>Top N Observational Candidates</h4>
              <div class="autopick-average-score">
                <strong id="autopick-average-score">N/A</strong>
                <span>Average score = sum(N scores) / N</span>
              </div>
            </div>
          </div>

          <div class="autopick-ranking-table-wrap">
            <table class="autopick-ranking-table">
              <thead>
                <tr>
                  <th>Rank</th>
                  <th>Symbol</th>
                  <th>Score</th>
                  <th>Spread</th>
                  <th>ATR</th>
                  <th>Volume Rel</th>
                  <th>Reasons</th>
                  <th>Selected</th>
                </tr>
              </thead>
              <tbody id="autopick-candidate-ranking-body">
                <tr>
                  <td colspan="8">No candidate ranking loaded.</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section class="autopick-panel" aria-label="Auto-pick execution trace">
          <div class="autopick-panel-header">
            <div>
              <span class="autopick-card-label">Auto-pick Trace</span>
              <h4>Read-only Step Tracking</h4>
            </div>
          </div>
          <section id="autopick-trace-rows" class="autopick-trace-horizontal">No auto-pick trace loaded.</section>
        </section>

        <section class="autopick-panel" aria-label="Auto-pick raw response">
          <div class="autopick-panel-header">
            <div>
              <span class="autopick-card-label">Backend Snapshot</span>
              <h4>Authoritative Auto-pick Payload</h4>
            </div>
            <button id="autopick-refresh-button" type="button" class="autopick-refresh-button">Refresh</button>
          </div>

          <pre id="autopick-status-output" class="autopick-output">No auto-pick status loaded.</pre>
        </section>
      </section>
    `;
  }

  function renderState(status) {
    if (!root || !window.AutopickStatusPresenter) {
      return;
    }

    const view = window.AutopickStatusPresenter.present(status);

    setText('#autopick-scheduler-state', view.schedulerState);
    setText('#autopick-interval', `Interval: ${view.interval}`);
    setText('#autopick-mode', view.dryRun);
    setText('#autopick-trading-state', `Trading: ${view.tradingState}`);
    setText('#autopick-last-tick-status', view.lastTickStatus);
    setText('#autopick-last-tick-at', view.lastTickAt);
    setText('#autopick-lock-state', view.lockState);
    setText('#autopick-duration', `Duration: ${view.duration} | Stale: ${view.staleState} | Age: ${view.staleDuration}`);
    setText('#autopick-candidate', view.candidate);
    setText('#autopick-score', `Score: ${view.score}`);
    setText('#autopick-execution-mode', view.executionMode);
    setText('#autopick-last-error', `Last error: ${view.lastError}`);
    const observation = view.observationSummary || {};
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
