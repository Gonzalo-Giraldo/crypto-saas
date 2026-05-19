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
    const output = root ? root.querySelector('#runtime-status-output') : null;
    if (!output) {
      return;
    }

    output.textContent = value;
    output.classList.toggle('is-error', Boolean(isError));
  }

  function getTemplate() {
    return `
      <section class="runtime-status" aria-label="Runtime Status module">
        <header class="runtime-status-header">
          <div>
            <h3>Runtime Status</h3>
            <p>Operational control view for real-money runtime readiness, kill-switch state, scheduler posture, and protection alerts.</p>
          </div>
        </header>

        <section class="runtime-grid" aria-label="Runtime status cards">
          <article class="runtime-card">
            <span class="runtime-card-label">Trading</span>
            <strong id="runtime-trading-enabled">UNKNOWN</strong>
            <p id="runtime-trading-detail">Waiting for backend status.</p>
          </article>

          <article class="runtime-card">
            <span class="runtime-card-label">Scheduler</span>
            <strong id="runtime-scheduler-enabled">UNKNOWN</strong>
            <p id="runtime-scheduler-detail">Waiting for backend status.</p>
          </article>

          <article class="runtime-card">
            <span class="runtime-card-label">Environment</span>
            <strong id="runtime-environment">UNKNOWN</strong>
            <p id="runtime-environment-detail">Backend authority only.</p>
          </article>

          <article class="runtime-card">
            <span class="runtime-card-label">Protection Alerts</span>
            <strong id="runtime-protection-alerts">UNKNOWN</strong>
            <p id="runtime-protection-detail">UNKNOWN and cleanup states must block automation.</p>
          </article>

          <article class="runtime-card">
            <span class="runtime-card-label">Runtime Authority</span>
            <strong id="runtime-authority-state">UNKNOWN</strong>
            <p id="runtime-authority-detail">Waiting for authority projection.</p>
          </article>

          <article class="runtime-card">
            <span class="runtime-card-label">Advisory Session</span>
            <strong id="runtime-advisory-state">UNKNOWN</strong>
            <p id="runtime-advisory-detail">Waiting for advisory state.</p>
          </article>

          <article class="runtime-card">
            <span class="runtime-card-label">Ownership</span>
            <strong id="runtime-ownership-state">UNKNOWN</strong>
            <p id="runtime-ownership-detail">Waiting for ownership lifecycle.</p>
          </article>

          <article class="runtime-card">
            <span class="runtime-card-label">Generation</span>
            <strong id="runtime-generation-state">UNKNOWN</strong>
            <p id="runtime-generation-detail">Waiting for generation reconciliation.</p>
          </article>

          <article class="runtime-card">
            <span class="runtime-card-label">Operator Attention</span>
            <strong id="runtime-operator-attention">UNKNOWN</strong>
            <p id="runtime-operator-attention-detail">Waiting for operational signals.</p>
          </article>
        </section>

        <section class="runtime-panel" aria-label="Runtime raw response">
          <div class="runtime-panel-header">
            <div>
              <span class="runtime-card-label">Backend Snapshot</span>
              <h4>Authoritative Runtime Payload</h4>
            </div>
            <button id="runtime-refresh-button" type="button" class="runtime-button">Refresh</button>
          </div>

          <pre id="runtime-status-output" class="runtime-console">No runtime status loaded.</pre>
        </section>
      </section>
    `;
  }

  function renderState(runtimeStatus) {
    if (!root || !window.RuntimeStatusPresenter) {
      return;
    }

    const view = window.RuntimeStatusPresenter.present(runtimeStatus);

    setText('#runtime-trading-enabled', view.tradingState);
    setText('#runtime-trading-detail', view.tradingDetail);
    setText('#runtime-scheduler-enabled', view.schedulerState);
    setText('#runtime-scheduler-detail', view.schedulerDetail);
    setText('#runtime-environment', view.environment);
    setText('#runtime-environment-detail', view.environmentDetail);
    setText('#runtime-protection-alerts', view.protectionAlerts);
    setText('#runtime-protection-detail', view.protectionDetail);
    setText('#runtime-authority-state', view.authorityState);
    setText('#runtime-authority-detail', view.authorityDetail);
    setText('#runtime-advisory-state', view.advisoryState);
    setText('#runtime-advisory-detail', view.advisoryDetail);
    setText('#runtime-ownership-state', view.ownershipState);
    setText('#runtime-ownership-detail', view.ownershipDetail);
    setText('#runtime-generation-state', view.generationState);
    setText('#runtime-generation-detail', view.generationDetail);
    setText('#runtime-operator-attention', view.operatorAttentionState);
    setText('#runtime-operator-attention-detail', view.operatorAttentionDetail);
    setOutput(view.loading ? 'Loading runtime status...' : view.rawText, view.isError);
  }

  function mount(target, orchestrator) {
    root = target;

    if (window.RuntimeStatusController) {
      window.RuntimeStatusController.start();
    }

    if (!root) {
      return;
    }

    root.innerHTML = getTemplate();

    const refreshButton = root.querySelector('#runtime-refresh-button');
    if (refreshButton) {
      refreshButton.addEventListener('click', () => {
        orchestrator.dispatch('runtime-status:refresh-requested');
      });
    }

    if (window.ControlCenterEventBus) {
      unsubscribe = window.ControlCenterEventBus.subscribe(
        'store:runtime-status:changed',
        renderState
      );
    }

    renderState(window.ControlCenterStore.getState().runtimeStatus);
    orchestrator.dispatch('runtime-status:refresh-requested');
  }

  function unmount() {
    if (typeof unsubscribe === 'function') {
      unsubscribe();
      unsubscribe = null;
    }

    if (window.RuntimeStatusController) {
      window.RuntimeStatusController.stop();
    }

    root = null;
  }

  window.RuntimeStatusModule = {
    id: 'runtime-status',
    title: 'Runtime Status',
    mount,
    unmount
  };
})();
