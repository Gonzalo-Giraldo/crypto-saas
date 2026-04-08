// Responsibility: Minimal reusable HTTP client for browser-based requests.

(function () {
  function getBaseUrl() {
    if (window.SharedConfig && typeof window.SharedConfig.getBaseUrl === 'function') {
      return window.SharedConfig.getBaseUrl() || '';
    }

    return '';
  }

  function buildUrl(endpoint) {
    const baseUrl = getBaseUrl();

    if (!baseUrl) {
      return endpoint;
    }

    const normalizedBaseUrl = baseUrl.endsWith('/') ? baseUrl.slice(0, -1) : baseUrl;
    const normalizedEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;

    return `${normalizedBaseUrl}${normalizedEndpoint}`;
  }

  async function executeHttpRequest(config) {
    const method = config && config.method ? config.method : 'GET';
    const endpoint = config && config.endpoint ? config.endpoint : '/';
    const headers = config && config.headers ? config.headers : {};
    const requestUrl = buildUrl(endpoint);

    const startedAt = performance.now();

    try {
      const response = await fetch(requestUrl, {
        method: method,
        headers: headers
      });

      const rawBody = await response.text();
      const durationMs = performance.now() - startedAt;

      return {
        ok: response.ok,
        status: response.status,
        statusText: response.statusText,
        rawBody: rawBody,
        durationMs: durationMs,
        requestUrl: requestUrl
      };
    } catch (error) {
      const durationMs = performance.now() - startedAt;
      const message = error && error.message ? error.message : 'Unknown network error';

      return {
        ok: false,
        status: 0,
        statusText: 'Network Error',
        rawBody: `Network or execution error:\n${message}`,
        durationMs: durationMs,
        requestUrl: requestUrl
      };
    }
  }

  window.SharedApiClient = {
    executeHttpRequest: executeHttpRequest
  };
})();
