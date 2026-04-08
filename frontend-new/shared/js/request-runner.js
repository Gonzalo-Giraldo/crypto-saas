// Responsibility: Minimal reusable test runner that normalizes HTTP execution results for UI modules.

(function () {
  function normalizeResult(testDefinition, httpResult) {
    return {
      testName: testDefinition.name,
      endpoint: testDefinition.endpoint,
      status: httpResult.status === 0
        ? 'Request failed'
        : `${httpResult.status} ${httpResult.statusText}`.trim(),
      durationText: `${httpResult.durationMs.toFixed(2)} ms`,
      bodyText: httpResult.rawBody || '[empty response body]',
      isError: !httpResult.ok
    };
  }

  async function runTestDefinition(testDefinition) {
    if (!window.SharedApiClient || !window.SharedApiClient.executeHttpRequest) {
      return {
        testName: testDefinition.name,
        endpoint: testDefinition.endpoint,
        status: 'Request failed',
        durationText: '0.00 ms',
        bodyText: 'SharedApiClient is not available.',
        isError: true
      };
    }

    const httpResult = await window.SharedApiClient.executeHttpRequest({
      method: testDefinition.method || 'GET',
      endpoint: testDefinition.endpoint,
      headers: testDefinition.headers || {
        Accept: 'application/json, text/plain, */*'
      }
    });

    return normalizeResult(testDefinition, httpResult);
  }

  window.SharedRequestRunner = {
    runTestDefinition: runTestDefinition
  };
})();
