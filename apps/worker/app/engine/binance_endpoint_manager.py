"""
Minimal groundwork for Binance endpoint failover management.
No real network probing or persistence in this step.
"""

class BinanceEndpointManager:
    def __init__(self, endpoints=None):
        # endpoints: list of endpoint URLs, primary first
        self._endpoints = endpoints or ["https://api.binance.com"]
        self._failed = set()
        self._current_idx = 0

    def get_active_endpoint(self):
        # Return the first non-failed endpoint
        for i, ep in enumerate(self._endpoints):
            if ep not in self._failed:
                self._current_idx = i
                return ep
        # If all failed, return primary
        self._current_idx = 0
        return self._endpoints[0]

    def mark_endpoint_failed(self, endpoint):
        self._failed.add(endpoint)

    def reset(self):
        self._failed.clear()
        self._current_idx = 0

    def get_all_endpoints(self):
        return list(self._endpoints)
