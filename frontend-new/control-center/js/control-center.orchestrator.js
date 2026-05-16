(function () {
  const modules = [];
  let activeModule = null;

  function registerModule(moduleDefinition) {
    if (
      !moduleDefinition ||
      !moduleDefinition.id ||
      !moduleDefinition.title ||
      typeof moduleDefinition.mount !== 'function'
    ) {
      return;
    }

    if (modules.some((registeredModule) => registeredModule.id === moduleDefinition.id)) {
      return;
    }

    modules.push(moduleDefinition);
  }

  function getModules() {
    return modules.slice();
  }

  function getModule(moduleId) {
    return modules.find((moduleDefinition) => moduleDefinition.id === moduleId) || null;
  }

  function mountModule(moduleId, target) {
    const moduleDefinition = getModule(moduleId);

    if (!moduleDefinition || !target) {
      return false;
    }

    if (
      activeModule &&
      activeModule.id !== moduleDefinition.id &&
      typeof activeModule.unmount === 'function'
    ) {
      activeModule.unmount();
    }

    target.innerHTML = '';
    moduleDefinition.mount(target, api);
    activeModule = moduleDefinition;

    return true;
  }

  function dispatch(eventName, payload) {
    if (window.ControlCenterEventBus) {
      window.ControlCenterEventBus.publish(eventName, payload);
    }
  }

  const api = {
    dispatch,
    getModules,
    mountModule
  };

  window.ControlCenterOrchestrator = {
    registerModule,
    getModules,
    getModule,
    mountModule,
    dispatch
  };
})();
