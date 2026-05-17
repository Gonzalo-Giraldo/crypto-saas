// Responsibility: Control-center shell wiring. Module registration and mounting go through ControlCenterOrchestrator only.

(function () {
  const menuContainer = document.querySelector('.module-nav');
  const accessContainer = document.querySelector('.cc-access');
  const refreshButton = document.getElementById('cc-refresh-button');
  const logoutButton = document.getElementById('cc-logout-button');
  const activeModuleTitle = document.getElementById('active-module-title');
  const activeModuleRoot = document.getElementById('active-module-root');

  let activeModuleId = 'session-gateway';

  const MODULE_ICONS = {
    'session-gateway': '⌂',
    'admin-tracking': '◫',
    'runtime-status': '◌',
    'autopick-status': '◎',
    'broker-placeholder': '◈',
    'broker-connectivity': '▣',
    'testing-center': '△'
  };


  function registerAvailableModules() {
    if (!window.ControlCenterOrchestrator) {
      return;
    }

    [
      window.SessionGatewayModule,
      window.AdminTrackingModule,
      window.BrokerPlaceholderModule,
      window.RuntimeStatusModule,
      window.AutopickStatusModule,
      window.TestingCenterModule,
      window.BrokerConnectivityModule
    ].forEach((moduleDefinition) => {
      window.ControlCenterOrchestrator.registerModule(moduleDefinition);
    });
  }

  function getSession() {
    if (!window.SessionStore || typeof window.SessionStore.getSession !== 'function') {
      return {
        sessionActive: false,
        role: null,
        broker: null,
      };
    }

    return window.SessionStore.getSession();
  }

  function isModuleVisibleForSession(moduleEntry, session) {
    if (!session || !session.sessionActive) {
      return moduleEntry.id === 'session-gateway';
    }

    if (session.role === 'ADMIN') {
      return [
        'session-gateway',
        'admin-tracking',
      ].includes(moduleEntry.id);
    }

    if (session.broker === 'BINANCE' || session.broker === 'IBKR') {
      return [
        'session-gateway',
        'broker-placeholder',
      ].includes(moduleEntry.id);
    }

    return moduleEntry.id === 'session-gateway';
  }

  function getModuleEntries() {
    if (!window.ControlCenterOrchestrator) {
      return [];
    }

    const session = getSession();

    return window.ControlCenterOrchestrator
      .getModules()
      .filter((moduleEntry) => isModuleVisibleForSession(moduleEntry, session));
  }

  function setActiveMenuState() {
    const buttons = menuContainer.querySelectorAll('[data-module]');

    buttons.forEach((button) => {
      const isActive = button.dataset.module === activeModuleId;
      button.classList.toggle('is-active', isActive);

      if (isActive) {
        button.setAttribute('aria-current', 'page');
      } else {
        button.removeAttribute('aria-current');
      }
    });
  }

  function mountActiveModule() {
    const activeModule = window.ControlCenterOrchestrator.getModule(activeModuleId);

    if (!activeModule || !activeModuleRoot || !activeModuleTitle) {
      return;
    }

    activeModuleTitle.textContent = activeModule.title;
    window.ControlCenterOrchestrator.mountModule(activeModuleId, activeModuleRoot);
    setActiveMenuState();
  }

  function setActiveModule(moduleId) {
    if (!window.ControlCenterOrchestrator.getModule(moduleId)) {
      return;
    }

    activeModuleId = moduleId;
    mountActiveModule();
  }

  function moduleForSession(session) {
    if (!session || !session.sessionActive) {
      return 'session-gateway';
    }

    if (session.role === 'ADMIN') {
      return 'admin-tracking';
    }

    if (session.broker === 'BINANCE') {
      return 'broker-placeholder';
    }

    if (session.broker === 'IBKR') {
      return 'broker-placeholder';
    }

    return 'session-gateway';
  }

  function setActiveAccessState(session) {
    if (!accessContainer) {
      return;
    }

    accessContainer.querySelectorAll('[data-access]').forEach((button) => {
      const access = button.dataset.access;
      const isActive =
        (access === 'admin' && session && session.role === 'ADMIN') ||
        (access === 'binance' && session && session.broker === 'BINANCE') ||
        (access === 'ibkr' && session && session.broker === 'IBKR');

      button.classList.toggle('is-active', Boolean(isActive));
      button.setAttribute('aria-current', isActive ? 'page' : 'false');
    });
  }

  function bindAccessRouting() {
    if (!accessContainer || !window.SessionStore) {
      return;
    }

    accessContainer.querySelectorAll('[data-access]').forEach((button) => {
      button.addEventListener('click', () => {
        const access = button.dataset.access;

        if (access === 'admin') {
          window.SessionStore.setSession({ sessionActive: true, role: 'ADMIN', broker: null });
          return;
        }

        if (access === 'binance') {
          window.SessionStore.setSession({ sessionActive: true, role: 'BROKER_USER', broker: 'BINANCE' });
          return;
        }

        if (access === 'ibkr') {
          window.SessionStore.setSession({ sessionActive: true, role: 'BROKER_USER', broker: 'IBKR' });
        }
      });
    });
  }

  function bindShellActions() {
    if (refreshButton && window.ControlCenterEventBus) {
      refreshButton.addEventListener('click', () => {
        window.ControlCenterEventBus.publish('runtime:refresh');
      });
    }

    if (logoutButton && window.SessionStore) {
      logoutButton.addEventListener('click', () => {
        window.SessionStore.clearSession();
      });
    }
  }

  function bindSessionRouting() {
    if (!window.ControlCenterEventBus) {
      return;
    }

    window.ControlCenterEventBus.subscribe('session:changed', (session) => {
      renderMenu();
      setActiveAccessState(session);
      setActiveModule(moduleForSession(session));
    });
  }

  function createMenuButton(moduleEntry) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'nav-item';
    button.dataset.module = moduleEntry.id;

    const icon = MODULE_ICONS[moduleEntry.id] || '•';

    button.innerHTML = `
      <span class="cc-nav-icon">${icon}</span>
      <span class="cc-nav-label">${moduleEntry.title}</span>
    `;

    button.addEventListener('click', () => {
      setActiveModule(moduleEntry.id);
    });

    return button;
  }

  function renderMenu() {
    if (!menuContainer) {
      return;
    }

    menuContainer.innerHTML = '';
    getModuleEntries().forEach((moduleEntry) => {
      menuContainer.appendChild(createMenuButton(moduleEntry));
    });
  }

  function initControlCenter() {
    if (
      !window.ControlCenterOrchestrator ||
      !menuContainer ||
      !activeModuleTitle ||
      !activeModuleRoot
    ) {
      return;
    }

    registerAvailableModules();
    renderMenu();
    bindAccessRouting();
    bindShellActions();
    bindSessionRouting();
    setActiveAccessState(getSession());
    setActiveModule(activeModuleId);
  }

  initControlCenter();
})();
