"""
Minimal groundwork for Binance User Data Stream event normalization.
No real websocket/networking in this step.
"""

class BinanceStreamListener:
    def __init__(self):
        pass  # No state yet

    def normalize_event(self, raw_event: dict) -> dict:
        """
        Accepts a raw broker event payload and returns a normalized event dict.
        Handles executionReport, order trade update, and account update events.
        Unknown/missing fields are handled safely.
        """
        event_type = raw_event.get("e") or raw_event.get("eventType")
        normalized = {"event_type": event_type}

        # Normalize executionReport/order trade update
        if event_type in ("executionReport", "ORDER_TRADE_UPDATE"):
            normalized.update({
                "order_id": raw_event.get("i") or raw_event.get("orderId"),
                "client_order_id": raw_event.get("c") or raw_event.get("clientOrderId"),
                "symbol": raw_event.get("s") or raw_event.get("symbol"),
                "side": raw_event.get("S") or raw_event.get("side"),
                "status": raw_event.get("X") or raw_event.get("orderStatus"),
                "filled_qty": raw_event.get("z") or raw_event.get("filledQty"),
                "cum_quote": raw_event.get("Z") or raw_event.get("cumQuote"),
                "event_time": raw_event.get("E") or raw_event.get("eventTime"),
            })
        # Normalize account update
        elif event_type in ("outboundAccountPosition", "ACCOUNT_UPDATE"):
            normalized.update({
                "balances": raw_event.get("B") or raw_event.get("balances"),
                "event_time": raw_event.get("E") or raw_event.get("eventTime"),
            })
        # Unknown event types: just return event_type and raw
        normalized["raw"] = raw_event
        return normalized
