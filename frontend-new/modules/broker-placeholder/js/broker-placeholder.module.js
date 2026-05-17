(function () {
  function sessionLabel() {
    const session = window.SessionStore ? window.SessionStore.getSession() : {};
    return session && session.broker ? session.broker : 'BROKER';
  }

  function mount(root) {
    if (!root) {
      return;
    }

    root.innerHTML = `
      <section class="broker-placeholder">
        <header class="broker-placeholder-header">
          <h3>${sessionLabel()} Access</h3>
          <p>Broker user screen reserved for future authenticated broker controls.</p>
        </header>

        <article class="broker-placeholder-card">
          <strong>No operational action enabled.</strong>
          <span>Real users, credentials, 2FA, and broker activation controls remain pending.</span>
        </article>
      </section>
    `;
  }

  window.BrokerPlaceholderModule = {
    id: 'broker-placeholder',
    title: 'Broker Access',
    mount,
  };
})();
