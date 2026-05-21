(function () {
  const runtimeStatusEndpoint = '/api/runtime/autopick-observation-status';

  async function fetchAutopickStatus() {
    if (!window.SharedApiClient || !window.SharedApiClient.executeHttpRequest) {
      throw new Error('SharedApiClient is not available.');
    }

    const result = await window.SharedApiClient.executeHttpRequest({
      method: 'GET',
      endpoint: runtimeStatusEndpoint,
      headers: {
        Accept: 'application/json, text/plain, */*'
      }
    });

    let payload = null;
    try {
      payload = result.rawBody ? JSON.parse(result.rawBody) : null;
    } catch (_error) {
      payload = null;
    }

    return {
      ok: Boolean(result.ok),
      status: result.status,
      statusText: result.statusText,
      rawBody: result.rawBody,
      payload
    };
  }

  window.AutopickStatusService = {
    fetchAutopickStatus
  };
})();
