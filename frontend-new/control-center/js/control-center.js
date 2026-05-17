// Responsibility: Control-center shell wiring. Module registration and mounting go through ControlCenterOrchestrator only.

(function () {
  const menuContainer = document.querySelector('.module-nav');
  const activeModuleTitle = document.getElementById('active-module-title');
  const activeModuleRoot = document.getElementById('active-module-root');

  let activeModuleId = 'session-gateway';

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

  function bindSessionRouting() {
    if (!window.ControlCenterEventBus) {
      return;
    }

    window.ControlCenterEventBus.subscribe('session:changed', (session) => {
      renderMenu();
      setActiveModule(moduleForSession(session));
    });
  }

  function createMenuButton(moduleEntry) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'nav-item';
    button.dataset.module = moduleEntry.id;
    button.textContent = moduleEntry.title;

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
    bindSessionRouting();
    setActiveModule(activeModuleId);
  }

  initControlCenter();
})();
