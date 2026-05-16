(function () {
  const listenersByEvent = new Map();

  function subscribe(eventName, handler) {
    if (!eventName || typeof handler !== 'function') {
      return function noop() {};
    }

    const listeners = listenersByEvent.get(eventName) || new Set();
    listeners.add(handler);
    listenersByEvent.set(eventName, listeners);

    return function unsubscribe() {
      listeners.delete(handler);
    };
  }

  function publish(eventName, payload) {
    const listeners = listenersByEvent.get(eventName);
    if (!listeners) {
      return;
    }

    listeners.forEach((handler) => {
      handler(payload);
    });
  }

  window.ControlCenterEventBus = {
    subscribe,
    publish
  };
})();
