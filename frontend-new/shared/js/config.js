// Responsibility: Minimal central environment configuration for browser-based frontend modules.

(function () {
  const config = {
    currentEnvironment: 'local',
    environments: {
      local: 'http://localhost:8000',
      docker: 'http://localhost:8000'
    },
    getBaseUrl() {
      return this.environments[this.currentEnvironment] || '';
    },
    setEnvironment(name) {
      if (Object.prototype.hasOwnProperty.call(this.environments, name)) {
        this.currentEnvironment = name;
      }

      return this.currentEnvironment;
    }
  };

  window.SharedConfig = config;
})();
