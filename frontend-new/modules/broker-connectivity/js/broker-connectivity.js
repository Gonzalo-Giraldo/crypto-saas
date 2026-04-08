// Responsibility: Broker connectivity checks using shared runner and config with standardized module layout.

(function () {
  const tests = [
    { id: 'binance', name: 'Binance Account Status', endpoint: '/ops/execution/binance/account-status', method: 'GET' },
    { id: 'ibkr', name: 'IBKR Account Status', endpoint: '/ops/execution/ibkr/account-status', method: 'GET' }
  ];

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  function getEnvironmentName() {
    if (window.SharedConfig && window.SharedConfig.currentEnvironment) {
      return window.SharedConfig.currentEnvironment;
    }

    return 'direct';
  }

  function getBaseUrl() {
    if (window.SharedConfig && typeof window.SharedConfig.getBaseUrl === 'function') {
      return window.SharedConfig.getBaseUrl() || '[direct endpoint]';
    }

    return '[direct endpoint]';
  }

  function formatBody(rawBody) {
    try {
      const parsed = rawBody ? JSON.parse(rawBody) : null;
      return parsed === null ? '[empty response body]' : JSON.stringify(parsed, null, 2);
    } catch (parseError) {
      return rawBody || '[empty response body]';
    }
  }

  function getTemplate() {
    return `
      <section class="broker-connectivity" aria-label="Broker Connectivity module">
        <header class="broker-connectivity-header">
          <div>
            <h3>Broker Connectivity</h3>
            <p>Run broker connectivity checks against the active backend environment.</p>
          </div>
        </header>

        <div class="broker-connectivity-layout">
          <section class="broker-panel broker-panel-control" aria-label="Broker connectivity control panel">
            <span class="broker-card-label">Control</span>
            <h4>Execution Panel</h4>
            <p class="broker-panel-copy">Active environment: <strong id="bc-active-environment">${escapeHtml(getEnvironmentName())}</strong></p>
            <p class="broker-panel-copy">Base URL: <strong id="bc-active-base-url">${escapeHtml(getBaseUrl())}</strong></p>

            <div class="broker-form-row">
              <label for="bc-test-select" class="broker-label">Available Test</label>
              <select id="bc-test-select" class="broker-select">
                ${tests
                  .map(
                    (test) =>
                      `<option value="${escapeHtml(test.id)}">${escapeHtml(test.name)} → ${escapeHtml(test.endpoint)}</option>`
                  )
                  .join('')}
              </select>
            </div>

            <div class="broker-actions">
              <button id="bc-run-button" type="button" class="broker-button">Run GET Test</button>
            </div>

            <div id="bc-execution-summary" class="broker-execution-summary" aria-live="polite">
              <div class="broker-summary-row">
                <span class="broker-summary-label">Test</span>
                <span id="bc-summary-test" class="broker-summary-value">Not executed</span>
              </div>
              <div class="broker-summary-row">
                <span class="broker-summary-label">Endpoint</span>
                <span id="bc-summary-endpoint" class="broker-summary-value">—</span>
              </div>
              <div class="broker-summary-row">
                <span class="broker-summary-label">Status</span>
                <span id="bc-summary-status" class="broker-summary-value">—</span>
              </div>
              <div class="broker-summary-row">
                <span class="broker-summary-label">Duration</span>
                <span id="bc-summary-duration" class="broker-summary-value">—</span>
              </div>
            </div>
          </section>

          <section class="broker-panel broker-panel-result" aria-label="Broker connectivity execution result">
            <span class="broker-card-label">Response</span>
            <h4>Response Body</h4>
            <p class="broker-panel-copy">The raw response body or execution error is shown below.</p>

            <pre id="bc-response-output" class="broker-response-console">No execution yet.</pre>
          </section>
        </div>
      </section>
    `;
  }

  function getSelectedTest(container) {
    const select = container.querySelector('#bc-test-select');
    return tests.find((test) => test.id === select.value) || tests[0];
  }

  function setSummary(container, values) {
    const summaryTest = container.querySelector('#bc-summary-test');
    const summaryEndpoint = container.querySelector('#bc-summary-endpoint');
    const summaryStatus = container.querySelector('#bc-summary-status');
    const summaryDuration = container.querySelector('#bc-summary-duration');

    summaryTest.textContent = values.test;
    summaryEndpoint.textContent = values.endpoint;
    summaryStatus.textContent = values.status;
    summaryDuration.textContent = values.duration;
  }

  function setResponseOutput(container, content, isError) {
    const responseOutput = container.querySelector('#bc-response-output');
    responseOutput.textContent = content;
    responseOutput.classList.toggle('is-error', Boolean(isError));
  }

  function resetReadyState(container) {
    const selectedTest = getSelectedTest(container);

    setSummary(container, {
      test: selectedTest.name,
      endpoint: selectedTest.endpoint,
      status: 'Ready',
      duration: '—'
    });
    setResponseOutput(container, 'Ready to execute selected test.', false);
  }

  async function runSelectedTest(container) {
    const selectedTest = getSelectedTest(container);
    const runButton = container.querySelector('#bc-run-button');

    setSummary(container, {
      test: selectedTest.name,
      endpoint: selectedTest.endpoint,
      status: 'Running...',
      duration: 'Running...'
    });
    setResponseOutput(container, 'Executing request...', false);
    runButton.disabled = true;
    runButton.textContent = 'Running...';

    try {
      const result = await window.SharedRequestRunner.runTestDefinition(selectedTest);

      setSummary(container, {
        test: result.testName,
        endpoint: result.endpoint,
        status: result.status,
        duration: result.durationText
      });

      setResponseOutput(container, formatBody(result.bodyText), result.isError);
    } catch (error) {
      const message = error && error.message ? error.message : 'Unknown error';

      setSummary(container, {
        test: selectedTest.name,
        endpoint: selectedTest.endpoint,
        status: 'Request failed',
        duration: '0.00 ms'
      });

      setResponseOutput(container, `Network or execution error:\n${message}`, true);
    } finally {
      runButton.disabled = false;
      runButton.textContent = 'Run GET Test';
    }
  }

  function bindEvents(container) {
    const runButton = container.querySelector('#bc-run-button');
    const testSelect = container.querySelector('#bc-test-select');

    testSelect.addEventListener('change', () => {
      resetReadyState(container);
    });

    runButton.addEventListener('click', () => {
      runSelectedTest(container);
    });

    resetReadyState(container);
  }

  window.BrokerConnectivityModule = {
    render(target) {
      if (!target) {
        return;
      }

      target.innerHTML = getTemplate();
      bindEvents(target);
    }
  };
})();
