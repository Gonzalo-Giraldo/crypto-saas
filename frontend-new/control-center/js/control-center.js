// Responsibility: Control-center shell wiring. Module registration and mounting go through ControlCenterOrchestrator only.

(function () {
  const menuContainer = document.querySelector('.module-nav');
  const activeModuleTitle = document.getElementById('active-module-title');
  const activeModuleRoot = document.getElementById('active-module-root');

  let activeModuleId = 'runtime-status';

  function registerAvailableModules() {
    if (!window.ControlCenterOrchestrator) {
      return;
    }

    [
      window.RuntimeStatusModule,
      window.AutopickStatusModule,
      window.TestingCenterModule,
      window.BrokerConnectivityModule
    ].forEach((moduleDefinition) => {
      window.ControlCenterOrchestrator.registerModule(moduleDefinition);
    });
  }

  function getModuleEntries() {
    if (!window.ControlCenterOrchestrator) {
      return [];
    }

    return window.ControlCenterOrchestrator.getModules();
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
    setActiveModule(activeModuleId);
  }

  initControlCenter();
})();
