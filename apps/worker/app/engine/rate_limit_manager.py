class RateLimitManager:
    """
    Minimal in-process rate limit manager for Binance groundwork.
    Tracks last seen Retry-After value and exposes before/after hooks.
    No external dependencies, no persistence, no threading.
    """
    def __init__(self, broker: str):
        self.broker = broker.upper()
        self.last_retry_after = None  # seconds (float or int)
        self.last_retry_after_header = None
        self.last_error_code = None

    def before_request(self, endpoint: str = None):
        # In groundwork, does nothing but could check state in future
        pass

    def after_response(self, response):
        # Look for Binance-style Retry-After header
        retry_after = None
        if hasattr(response, 'headers'):
            retry_after = response.headers.get('Retry-After')
        if retry_after is not None:
            try:
                self.last_retry_after = float(retry_after)
                self.last_retry_after_header = retry_after
            except Exception:
                self.last_retry_after = None
        # Could add more broker-specific logic here in future

    def after_error(self, error, response=None):
        # Optionally track error code for groundwork
        if hasattr(error, 'status_code'):
            self.last_error_code = getattr(error, 'status_code', None)
        elif hasattr(error, 'response') and hasattr(error.response, 'status_code'):
            self.last_error_code = getattr(error.response, 'status_code', None)
        # Could add more broker-specific error handling here in future
        if response is not None:
            self.after_response(response)
