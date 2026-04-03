class SubmissionContractError(Exception):
    pass


def validate_submission_payload(payload: dict) -> bool:
    required = {"user_id", "broker", "request_id", "order_id", "symbol", "side", "qty"}

    if not isinstance(payload, dict):
        raise SubmissionContractError("Payload must be a dict")

    missing = required - set(payload)
    if missing:
        raise SubmissionContractError(f"Missing fields: {missing}")

    if payload["side"] not in ("BUY", "SELL"):
        raise SubmissionContractError("Invalid side")

    try:
        qty = float(payload["qty"])
    except Exception:
        raise SubmissionContractError("qty must be a number")

    if qty <= 0:
        raise SubmissionContractError("qty must be positive")

    return True


def is_valid_submission(payload):
    try:
        return validate_submission_payload(payload)
    except SubmissionContractError:
        return False
