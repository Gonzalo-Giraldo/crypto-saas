// Responsibility: Centralized module registry, menu rendering and active module mounting for control-center.

(function () {
  const moduleDefinitions = [
    {
      id: 'testing-center',
      title: 'Testing Center',
      getRender() {
        return window.TestingCenterModule && window.TestingCenterModule.render;
      }
    },
    {
      id: 'broker-connectivity',
      title: 'Broker Connectivity',
      getRender() {
        return window.BrokerConnectivityModule && window.BrokerConnectivityModule.render;
      }
    }
  ];

  const moduleRegistry = moduleDefinitions.reduce((registry, definition) => {
    registry[definition.id] = {
      id: definition.id,
      title: definition.title,
      render(target) {
        const renderFn = definition.getRender();

        if (typeof renderFn === 'function') {
          renderFn(target);
          return;
        }

        if (target) {
          target.innerHTML = '<p>Module is not available.</p>';
        }
      }
    };

    return registry;
  }, {});

  const menuContainer = document.querySelector('.module-nav');
  const activeModuleTitle = document.getElementById('active-module-title');
  const activeModuleRoot = document.getElementById('active-module-root');

  let activeModuleId = 'testing-center';

  function getModuleEntries() {
    return Object.values(moduleRegistry);
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
    const activeModule = moduleRegistry[activeModuleId];

    if (!activeModule || !activeModuleRoot || !activeModuleTitle) {
      return;
    }

    activeModuleTitle.textContent = activeModule.title;
    activeModule.render(activeModuleRoot);
    setActiveMenuState();
  }

  function setActiveModule(moduleId) {
    if (!moduleRegistry[moduleId]) {
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
    if (!menuContainer || !activeModuleTitle || !activeModuleRoot) {
      return;
    }

    renderMenu();
    setActiveModule('testing-center');
  }

  initControlCenter();
})();
