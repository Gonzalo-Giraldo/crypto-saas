// Responsibility: Minimal real GET execution for selected backend health endpoints using shared browser utilities,
// with in-memory execution history, quick rerun support and a fixed multi-step health suite.

(function () {
  const tests = [
    { id: 'health', name: 'Health', endpoint: '/health', method: 'GET' },
    { id: 'healthz', name: 'Healthz', endpoint: '/healthz', method: 'GET' },
    { id: 'ops-health', name: 'Ops Health', endpoint: '/ops/health', method: 'GET' }
  ];

  const healthCheckSuite = {
    id: 'health-check-suite',
    name: 'Health Check Suite',
    steps: ['health', 'healthz', 'ops-health']
  };

  const executionHistory = [];
  const maxHistoryEntries = 5;

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

  function getAvailableEnvironments() {
    if (window.SharedConfig && window.SharedConfig.environments) {
      return Object.keys(window.SharedConfig.environments);
    }

    return [];
  }

  function formatBody(rawBody) {
    try {
      const parsed = rawBody ? JSON.parse(rawBody) : null;
      return parsed === null ? '[empty response body]' : JSON.stringify(parsed, null, 2);
    } catch (parseError) {
      return rawBody || '[empty response body]';
    }
  }

  function getTimestamp() {
    const now = new Date();
    return now.toLocaleString();
  }

  function findTestById(testId) {
    return tests.find((test) => test.id === testId) || tests[0];
  }

  function findTestByEndpoint(endpoint) {
    return tests.find((test) => test.endpoint === endpoint) || tests[0];
  }

  function addHistoryEntry(entry) {
    executionHistory.unshift(entry);

    if (executionHistory.length > maxHistoryEntries) {
      executionHistory.length = maxHistoryEntries;
    }
  }

  function getTemplate() {
    const environmentOptions = getAvailableEnvironments()
      .map((environmentName) => {
        const isSelected = environmentName === getEnvironmentName() ? ' selected' : '';
        return `<option value="${escapeHtml(environmentName)}"${isSelected}>${escapeHtml(environmentName)}</option>`;
      })
      .join('');

    return `
      <section class="testing-center" aria-label="Testing Center module">
        <header class="testing-center-header">
          <div>
            <h3>Testing Center</h3>
            <p>Run controlled GET health checks against the live backend and inspect the response.</p>
          </div>
        </header>

        <div class="testing-center-layout">
          <section class="testing-panel testing-panel-control" aria-label="Test control panel">
            <span class="testing-card-label">Control</span>
            <h4>Execution Panel</h4>

            <div class="testing-form-row">
              <label for="environment-select" class="testing-label">Active Environment</label>
              <select id="environment-select" class="testing-select">
                ${environmentOptions}
              </select>
            </div>

            <p class="testing-panel-copy">Active environment: <strong id="active-environment">${escapeHtml(getEnvironmentName())}</strong></p>
            <p class="testing-panel-copy">Base URL: <strong id="active-base-url">${escapeHtml(getBaseUrl())}</strong></p>

            <div class="testing-form-row">
              <label for="test-select" class="testing-label">Available Test</label>
              <select id="test-select" class="testing-select">
                ${tests
                  .map(
                    (test) =>
                      `<option value="${escapeHtml(test.id)}">${escapeHtml(test.name)} → ${escapeHtml(test.endpoint)}</option>`
                  )
                  .join('')}
              </select>
            </div>

            <div class="testing-actions">
              <button id="run-test-button" type="button" class="testing-button">Run GET Test</button>
              <button id="run-suite-button" type="button" class="testing-button">Run Health Check Suite</button>
            </div>

            <div id="execution-summary" class="execution-summary" aria-live="polite">
              <div class="summary-row">
                <span class="summary-label">Execution</span>
                <span id="summary-execution" class="summary-value">Not executed</span>
              </div>
              <div class="summary-row">
                <span class="summary-label">Target</span>
                <span id="summary-test" class="summary-value">Not executed</span>
              </div>
              <div class="summary-row">
                <span class="summary-label">Endpoint</span>
                <span id="summary-endpoint" class="summary-value">—</span>
              </div>
              <div class="summary-row">
                <span class="summary-label">Status</span>
                <span id="summary-status" class="summary-value">—</span>
              </div>
              <div class="summary-row">
                <span class="summary-label">Duration</span>
                <span id="summary-duration" class="summary-value">—</span>
              </div>
            </div>
          </section>

          <section class="testing-panel testing-panel-result" aria-label="Execution result panel">
            <span class="testing-card-label">Response</span>
            <h4>Response Body</h4>
            <p class="testing-panel-copy">The raw response body or execution error is shown below.</p>

            <pre id="response-output" class="response-console">No execution yet.</pre>
          </section>
        </div>

        <section class="testing-panel" aria-label="Execution history">
          <span class="testing-card-label">History</span>
          <h4>Recent Executions</h4>
          <p class="testing-panel-copy">The latest five executions are kept in session memory and can be repeated.</p>
          <div id="history-list" class="execution-summary" aria-live="polite"></div>
        </section>
      </section>
    `;
  }

  function getSelectedTest(container) {
    const select = container.querySelector('#test-select');
    return findTestById(select.value);
  }

  function setSummary(container, values) {
    const summaryExecution = container.querySelector('#summary-execution');
    const summaryTest = container.querySelector('#summary-test');
    const summaryEndpoint = container.querySelector('#summary-endpoint');
    const summaryStatus = container.querySelector('#summary-status');
    const summaryDuration = container.querySelector('#summary-duration');

    summaryExecution.textContent = values.execution;
    summaryTest.textContent = values.test;
    summaryEndpoint.textContent = values.endpoint;
    summaryStatus.textContent = values.status;
    summaryDuration.textContent = values.duration;
  }

  function setResponseOutput(container, content, isError) {
    const responseOutput = container.querySelector('#response-output');
    responseOutput.textContent = content;
    responseOutput.classList.toggle('is-error', Boolean(isError));
  }

  function refreshEnvironmentDisplay(container) {
    const activeEnvironment = container.querySelector('#active-environment');
    const activeBaseUrl = container.querySelector('#active-base-url');

    if (activeEnvironment) {
      activeEnvironment.textContent = getEnvironmentName();
    }

    if (activeBaseUrl) {
      activeBaseUrl.textContent = getBaseUrl();
    }
  }

  function renderHistory(container) {
    const historyList = container.querySelector('#history-list');

    if (!historyList) {
      return;
    }

    if (!executionHistory.length) {
      historyList.innerHTML = '<div class="summary-row"><span class="summary-value">No executions recorded yet.</span></div>';
      return;
    }

    historyList.innerHTML = executionHistory
      .map((entry, index) => {
        return `
          <div class="summary-row" data-history-index="${index}">
            <span class="summary-label">${escapeHtml(entry.timestamp)}</span>
            <span class="summary-value"><strong>${escapeHtml(entry.testName)}</strong> · ${escapeHtml(entry.endpoint)}</span>
            <span class="summary-value">Environment: ${escapeHtml(entry.environment)} · Status: ${escapeHtml(entry.status)} · Duration: ${escapeHtml(entry.durationText)}</span>
            <div class="testing-actions">
              <button type="button" class="testing-button history-rerun-button" data-history-index="${index}">Repeat</button>
            </div>
          </div>
        `;
      })
      .join('');
  }

  function resetReadyState(container) {
    const selectedTest = getSelectedTest(container);

    setSummary(container, {
      execution: 'Individual',
      test: selectedTest.name,
      endpoint: selectedTest.endpoint,
      status: 'Ready',
      duration: '—'
    });
    setResponseOutput(container, 'Ready to execute selected test or suite.', false);
  }

  async function runSingleTest(selectedTest) {
    try {
      return await window.SharedRequestRunner.runTestDefinition(selectedTest);
    } catch (error) {
      const message = error && error.message ? error.message : 'Unknown error';

      return {
        testName: selectedTest.name,
        endpoint: selectedTest.endpoint,
        status: 'Request failed',
        durationText: '0.00 ms',
        bodyText: `Network or execution error:\n${message}`,
        isError: true
      };
    }
  }

  function buildSuiteOutput(stepResults, suiteStatus, durationText) {
    const lines = [
      `Suite: ${healthCheckSuite.name}`,
      `Status: ${suiteStatus}`,
      `Duration: ${durationText}`,
      '',
      'Steps:'
    ];

    stepResults.forEach((stepResult, index) => {
      lines.push(
        `${index + 1}. ${stepResult.testName}`,
        `   Endpoint: ${stepResult.endpoint}`,
        `   Status: ${stepResult.status}`,
        `   Duration: ${stepResult.durationText}`,
        '   Response:',
        `${indentBlock(formatBody(stepResult.bodyText), 6)}`,
        ''
      );
    });

    return lines.join('\n').trim();
  }

  function indentBlock(text, spaces) {
    const padding = ' '.repeat(spaces);
    return String(text)
      .split('\n')
      .map((line) => `${padding}${line}`)
      .join('\n');
  }

  async function executeTest(container, selectedTest) {
    const runButton = container.querySelector('#run-test-button');
    const suiteButton = container.querySelector('#run-suite-button');

    setSummary(container, {
      execution: 'Individual',
      test: selectedTest.name,
      endpoint: selectedTest.endpoint,
      status: 'Running...',
      duration: 'Running...'
    });
    setResponseOutput(container, 'Executing request...', false);
    runButton.disabled = true;
    suiteButton.disabled = true;
    runButton.textContent = 'Running...';

    try {
      const result = await runSingleTest(selectedTest);

      setSummary(container, {
        execution: 'Individual',
        test: result.testName,
        endpoint: result.endpoint,
        status: result.status,
        duration: result.durationText
      });

      setResponseOutput(container, formatBody(result.bodyText), result.isError);

      addHistoryEntry({
        testName: result.testName,
        endpoint: result.endpoint,
        environment: getEnvironmentName(),
        status: result.status,
        durationText: result.durationText,
        timestamp: getTimestamp(),
        executionType: 'single'
      });
      renderHistory(container);
    } finally {
      runButton.disabled = false;
      suiteButton.disabled = false;
      runButton.textContent = 'Run GET Test';
    }
  }

  async function executeSuite(container) {
    const runButton = container.querySelector('#run-test-button');
    const suiteButton = container.querySelector('#run-suite-button');
    const suiteSteps = healthCheckSuite.steps.map((stepId) => findTestById(stepId));
    const startedAt = performance.now();
    const stepResults = [];

    setSummary(container, {
      execution: 'Suite',
      test: healthCheckSuite.name,
      endpoint: '[suite]',
      status: 'Running...',
      duration: 'Running...'
    });
    setResponseOutput(container, 'Executing suite...', false);
    runButton.disabled = true;
    suiteButton.disabled = true;
    suiteButton.textContent = 'Running...';

    try {
      for (let index = 0; index < suiteSteps.length; index += 1) {
        const stepResult = await runSingleTest(suiteSteps[index]);
        stepResults.push(stepResult);
      }

      const totalDurationMs = performance.now() - startedAt;
      const durationText = `${totalDurationMs.toFixed(2)} ms`;
      const suiteStatus = stepResults.every((stepResult) => !stepResult.isError) ? 'PASS' : 'FAIL';

      setSummary(container, {
        execution: 'Suite',
        test: healthCheckSuite.name,
        endpoint: '[suite]',
        status: suiteStatus,
        duration: durationText
      });

      setResponseOutput(container, buildSuiteOutput(stepResults, suiteStatus, durationText), suiteStatus === 'FAIL');

      addHistoryEntry({
        testName: healthCheckSuite.name,
        endpoint: '[suite]',
        environment: getEnvironmentName(),
        status: suiteStatus,
        durationText: durationText,
        timestamp: getTimestamp(),
        executionType: 'suite'
      });
      renderHistory(container);
    } finally {
      runButton.disabled = false;
      suiteButton.disabled = false;
      suiteButton.textContent = 'Run Health Check Suite';
    }
  }

  async function rerunHistoryEntry(container, historyIndex) {
    const entry = executionHistory[historyIndex];

    if (!entry) {
      return;
    }

    const environmentSelect = container.querySelector('#environment-select');
    const testSelect = container.querySelector('#test-select');

    if (window.SharedConfig && typeof window.SharedConfig.setEnvironment === 'function') {
      window.SharedConfig.setEnvironment(entry.environment);
    }

    if (environmentSelect) {
      environmentSelect.value = entry.environment;
    }

    refreshEnvironmentDisplay(container);

    if (entry.executionType === 'suite' || entry.endpoint === '[suite]') {
      await executeSuite(container);
      return;
    }

    const matchedTest = findTestByEndpoint(entry.endpoint);

    if (testSelect) {
      testSelect.value = matchedTest.id;
    }

    await executeTest(container, matchedTest);
  }

  function bindEvents(container) {
    const runButton = container.querySelector('#run-test-button');
    const suiteButton = container.querySelector('#run-suite-button');
    const testSelect = container.querySelector('#test-select');
    const environmentSelect = container.querySelector('#environment-select');
    const historyList = container.querySelector('#history-list');

    environmentSelect.addEventListener('change', () => {
      if (window.SharedConfig && typeof window.SharedConfig.setEnvironment === 'function') {
        window.SharedConfig.setEnvironment(environmentSelect.value);
      }

      refreshEnvironmentDisplay(container);
      resetReadyState(container);
    });

    testSelect.addEventListener('change', () => {
      resetReadyState(container);
    });

    runButton.addEventListener('click', () => {
      executeTest(container, getSelectedTest(container));
    });

    suiteButton.addEventListener('click', () => {
      executeSuite(container);
    });

    historyList.addEventListener('click', (event) => {
      const rerunButton = event.target.closest('.history-rerun-button');

      if (!rerunButton) {
        return;
      }

      const historyIndex = Number(rerunButton.dataset.historyIndex);

      if (Number.isNaN(historyIndex)) {
        return;
      }

      rerunHistoryEntry(container, historyIndex);
    });

    refreshEnvironmentDisplay(container);
    resetReadyState(container);
    renderHistory(container);
  }

  window.TestingCenterModule = {
    render(target) {
      if (!target) {
        return;
      }

      target.innerHTML = getTemplate();
      bindEvents(target);
    }
  };
})();
