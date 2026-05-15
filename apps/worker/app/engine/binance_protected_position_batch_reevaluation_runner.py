from __future__ import annotations

from apps.worker.app.engine.binance_protected_position_runtime_context import (
    build_protected_position_runtime_context,
)
from apps.worker.app.engine.binance_protected_position_reevaluation_runner import (
    reevaluate_protected_position_once,
)
from apps.api.app.services.runtime_actions import ACTION_ACTIVATE_TRAILING


def reevaluate_active_protected_positions_once(
    *,
    protected_positions: list[dict],
    protection_reconciliation_by_exit_key: dict,
    sl_stop_price_by_exit_key: dict | None = None,
    fetch_current_price=None,
    owner_id: str | None = None,
    claim_transition=None,
    complete_transition=None,
    run_replacement=None,
) -> list[dict]:
    results: list[dict] = []

    for protected_position in protected_positions:
        exit_key = str((protected_position or {}).get("exit_key") or "").strip()

        if not exit_key:
            results.append(
                {
                    "exit_key": None,
                    "result": {
                        "status": "blocked",
                        "reason": "exit_key_required",
                    },
                }
            )
            continue

        claim_acquired = False

        try:
            protected_position_for_context = dict(protected_position)
            stop_price = (sl_stop_price_by_exit_key or {}).get(exit_key)
            if stop_price is not None:
                protected_position_for_context["stop_loss"] = stop_price

            context = build_protected_position_runtime_context(
                protected_position=protected_position_for_context,
                fetch_current_price=fetch_current_price,
            )

            if context.get("status") == "blocked":
                results.append(
                    {
                        "exit_key": exit_key,
                        "result": context,
                    }
                )
                continue

            protection_reconciliation = (
                protection_reconciliation_by_exit_key or {}
            ).get(exit_key)

            if not isinstance(protection_reconciliation, dict):
                results.append(
                    {
                        "exit_key": exit_key,
                        "result": {
                            "status": "blocked",
                            "reason": "protection_reconciliation_required",
                        },
                    }
                )
                continue

            transition_claim = None

            if not callable(claim_transition):
                results.append(
                    {
                        "exit_key": exit_key,
                        "result": {
                            "status": "blocked",
                            "reason": "transition_claim_required",
                        },
                    }
                )
                continue

            claim = claim_transition(
                exit_key=exit_key,
                required_action=ACTION_ACTIVATE_TRAILING,
                owner_id=owner_id,
            )

            if (claim or {}).get("status") != "claimed":
                results.append(
                    {
                        "exit_key": exit_key,
                        "result": {
                            "status": "blocked",
                            "reason": "transition_claim_not_owned",
                        },
                    }
                )
                continue

            claim_acquired = True
            transition_claim = {
                "claim_status": "ACTIVE",
                "exit_key": exit_key,
                "required_action": ACTION_ACTIVATE_TRAILING,
                "owner_id": owner_id,
            }

            result = reevaluate_protected_position_once(
                position=context["position"],
                protection_reconciliation=protection_reconciliation,
                old_sl_client_algo_id=context["old_sl_client_algo_id"],
                replacement_client_order_id=f"{exit_key}-TRAIL",
                transition_claim=transition_claim,
                run_replacement=run_replacement,
            )

            if callable(complete_transition):
                result_status = str(
                    result.get("status") or ""
                ).lower().strip()

                if result_status == "replaced":
                    final_status = "FINALIZED"
                elif result_status == "noop":
                    final_status = "RELEASED"
                else:
                    final_status = "ABANDONED"

                complete_transition(
                    exit_key=exit_key,
                    required_action=ACTION_ACTIVATE_TRAILING,
                    owner_id=owner_id,
                    final_status=final_status,
                )

            results.append(
                {
                    "exit_key": exit_key,
                    "result": result,
                }
            )

        except Exception as exc:
            lifecycle_cleanup_error = None

            if claim_acquired and callable(complete_transition):
                try:
                    complete_transition(
                        exit_key=exit_key,
                        required_action=ACTION_ACTIVATE_TRAILING,
                        owner_id=owner_id,
                        final_status="ABANDONED",
                    )
                except Exception as cleanup_exc:
                    lifecycle_cleanup_error = str(cleanup_exc)

            error_result = {
                "status": "blocked",
                "reason": "protected_position_reevaluation_error",
                "error": str(exc),
            }

            if lifecycle_cleanup_error is not None:
                error_result["lifecycle_cleanup_error"] = (
                    lifecycle_cleanup_error
                )

            results.append(
                {
                    "exit_key": exit_key,
                    "result": error_result,
                }
            )

    return results
