// Responsibility: Minimal central environment configuration for browser-based frontend modules.

(function () {
  const config = {
    currentEnvironment: 'local',
    environments: {
      local: 'http://127.0.0.1:8010',
      ec2: 'http://127.0.0.1:8010'
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
