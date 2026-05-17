(function () {
  const tabs = [
    {
      id: 'autopick',
      title: 'AUTOPICK',
      enabled: true,
      moduleId: 'autopick-status',
      unavailableText: 'Auto-pick status module is not available.',
    },
    {
      id: 'runtime',
      title: 'RUNTIME',
      enabled: true,
      moduleId: 'runtime-status',
      unavailableText: 'Runtime status module is not available.',
    },
    {
      id: 'broker',
      title: 'BROKER',
      enabled: true,
      moduleId: 'broker-connectivity',
      unavailableText: 'Broker connectivity module is not available.',
    },
    {
      id: 'testing',
      title: 'TESTING',
      enabled: true,
      moduleId: 'testing-center',
      unavailableText: 'Testing center module is not available.',
    },
  ];

  function getModule(moduleId) {
    if (!window.ControlCenterOrchestrator) {
      return null;
    }

    return window.ControlCenterOrchestrator.getModule(moduleId);
  }

  function renderTabs(activeTabId) {
    return tabs.map((tab) => `
      <button
        type="button"
        class="admin-tracking-tab ${tab.id === activeTabId ? 'is-active' : ''}"
        data-admin-tracking-tab="${tab.id}"
        ${tab.enabled ? '' : 'disabled'}
        aria-current="${tab.id === activeTabId ? 'page' : 'false'}">
        ${tab.title}
      </button>
    `).join('');
  }

  function renderTabContent(root, tabId) {
    const body = root.querySelector('#admin-tracking-body');
    if (!body) {
      return;
    }

    const tab = tabs.find((item) => item.id === tabId) || tabs[0];
    body.innerHTML = '<div id="admin-tracking-tab-root"></div>';

    const moduleRoot = body.querySelector('#admin-tracking-tab-root');
    const moduleDefinition = getModule(tab.moduleId);

    if (!moduleDefinition || typeof moduleDefinition.mount !== 'function') {
      moduleRoot.innerHTML = `
        <section class="admin-tracking-unavailable">
          <strong>${tab.title}</strong>
          <p>${tab.unavailableText}</p>
        </section>
      `;
      return;
    }

    moduleDefinition.mount(moduleRoot);
  }

  function setActiveTab(root, tabId) {
    root.querySelectorAll('[data-admin-tracking-tab]').forEach((tabButton) => {
      const isActive = tabButton.dataset.adminTrackingTab === tabId;
      tabButton.classList.toggle('is-active', isActive);
      tabButton.setAttribute('aria-current', isActive ? 'page' : 'false');
    });

    renderTabContent(root, tabId);
  }

  function bindTabs(root) {
    root.querySelectorAll('[data-admin-tracking-tab]').forEach((button) => {
      button.addEventListener('click', () => {
        if (button.disabled) {
          return;
        }

        setActiveTab(root, button.dataset.adminTrackingTab);
      });
    });
  }

  function mount(root) {
    if (!root) {
      return;
    }

    const defaultTabId = 'autopick';

    root.innerHTML = `
      <section class="admin-tracking">
        <header class="admin-tracking-header">
          <h3>Seguimiento</h3>
          <p>Verificación operacional de módulos backend.</p>
        </header>

        <nav class="admin-tracking-tabs" aria-label="Backend module tracking tabs">
          ${renderTabs(defaultTabId)}
        </nav>

        <section id="admin-tracking-body" class="admin-tracking-body"></section>
      </section>
    `;

    bindTabs(root);
    renderTabContent(root, defaultTabId);
  }

  window.AdminTrackingModule = {
    id: 'admin-tracking',
    title: 'Seguimiento',
    mount,
  };
})();
