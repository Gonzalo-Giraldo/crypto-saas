(function () {
  function activateSession(type) {
    if (!window.SessionStore) {
      return;
    }

    if (type === 'admin') {
      window.SessionStore.setSession({
        sessionActive: true,
        role: 'ADMIN',
        broker: null,
      });
      return;
    }

    if (type === 'binance') {
      window.SessionStore.setSession({
        sessionActive: true,
        role: 'BROKER_USER',
        broker: 'BINANCE',
      });
      return;
    }

    if (type === 'ibkr') {
      window.SessionStore.setSession({
        sessionActive: true,
        role: 'BROKER_USER',
        broker: 'IBKR',
      });
    }
  }

  function renderSessionGateway(root) {
    if (!root) {
      return;
    }

    root.innerHTML = `
      <section class="session-gateway">
        <header class="session-gateway-header">
          <h3>Runtime Access</h3>
          <p>Temporary visual routing. Backend authentication will be connected in the final frontend phase.</p>
        </header>

        <div class="session-gateway-grid">
          <button class="session-card" data-session="admin">
            <strong>Administrator</strong>
            <span>Go to administration options.</span>
          </button>

          <button class="session-card" data-session="binance">
            <strong>Binance</strong>
            <span>Broker user access placeholder.</span>
          </button>

          <button class="session-card" data-session="ibkr">
            <strong>IBKR</strong>
            <span>Broker user access placeholder.</span>
          </button>
        </div>
      </section>
    `;

    root.querySelectorAll('[data-session]').forEach((button) => {
      button.addEventListener('click', () => {
        activateSession(button.dataset.session);
      });
    });
  }

  window.SessionGatewayModule = {
    id: 'session-gateway',
    title: 'Runtime Access',
    mount: renderSessionGateway,
  };
})();
