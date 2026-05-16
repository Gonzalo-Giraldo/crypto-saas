(function () {
  let root = null;
  let unsubscribe = null;

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

  function getTemplate() {
    return `
      <section class="autopick-status" aria-label="Auto-pick Status module">
        <header class="autopick-status-header">
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

        <section class="autopick-panel" aria-label="Auto-pick raw response">
          <div class="autopick-panel-header">
            <div>
              <span class="autopick-card-label">Backend Snapshot</span>
              <h4>Authoritative Auto-pick Payload</h4>
            </div>
            <button id="autopick-refresh-button" type="button" class="autopick-button">Refresh</button>
          </div>

          <pre id="autopick-status-output" class="autopick-console">No auto-pick status loaded.</pre>
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
    setOutput(view.loading ? 'Loading auto-pick status...' : view.rawText, view.isError);
  }

  function mount(target, orchestrator) {
    root = target;

    if (window.AutopickStatusController) {
      window.AutopickStatusController.start();
    }

    if (!root) {
      return;
    }

    root.innerHTML = getTemplate();

    const refreshButton = root.querySelector('#autopick-refresh-button');
    if (refreshButton) {
      refreshButton.addEventListener('click', () => {
        orchestrator.dispatch('autopick-status:refresh-requested');
      });
    }

    if (window.ControlCenterEventBus) {
      unsubscribe = window.ControlCenterEventBus.subscribe(
        'store:autopick-status:changed',
        renderState
      );
    }

    renderState(window.ControlCenterStore.getState().autopickStatus);
    orchestrator.dispatch('autopick-status:refresh-requested');
  }

  function unmount() {
    if (typeof unsubscribe === 'function') {
      unsubscribe();
      unsubscribe = null;
    }

    if (window.AutopickStatusController) {
      window.AutopickStatusController.stop();
    }

    root = null;
  }

  window.AutopickStatusModule = {
    id: 'autopick-status',
    title: 'Auto-pick Status',
    mount,
    unmount
  };
})();
