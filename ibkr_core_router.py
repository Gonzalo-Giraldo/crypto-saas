from m_ibkr_bridge.order_module import handle_order
from m_ibkr_bridge.status_module import handle_status
from m_ibkr_bridge.health_module import handle_health

def route(action, payload=None):
    if action == "order":
        return handle_order(payload)
    elif action == "status":
        return handle_status()
    elif action == "health":
        return handle_health()
    else:
        return {"success": False, "error": "unknown_action"}
