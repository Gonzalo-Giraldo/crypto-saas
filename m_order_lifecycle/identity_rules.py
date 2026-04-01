# MODULE: identity_rules
# PURPOSE: define strong identity rules for multi-user, multi-broker trading system


def build_order_identity(user_id: str, broker: str, request_id: str) -> str:
    """
    Identity of an order at intent stage
    """
    return f"{user_id}::{broker}::{request_id}"


def build_broker_order_identity(user_id: str, broker: str, broker_order_id: str) -> str:
    """
    Identity of an order once acknowledged by broker
    """
    return f"{user_id}::{broker}::{broker_order_id}"


def build_fill_identity(
    user_id: str,
    broker: str,
    exec_id: str,
    executed_at_precise: str,
) -> str:
    """
    Identity of a fill (execution)
    Must include precise timestamp to avoid collisions
    """
    return f"{user_id}::{broker}::{exec_id}::{executed_at_precise}"


def build_reconciliation_identity(
    user_id: str,
    broker: str,
    parent_order_identity: str,
) -> str:
    """
    One reconciliation line per order
    """
    return f"{user_id}::{broker}::{parent_order_identity}::recon"


def build_pnl_identity(
    user_id: str,
    broker: str,
    parent_order_identity: str,
) -> str:
    """
    One PnL line per order
    """
    return f"{user_id}::{broker}::{parent_order_identity}::pnl"
