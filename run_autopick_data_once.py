from apps.api.app.services.auto_pick.binance.orchestrator import (
    run_binance_auto_pick_observation,
)
from apps.api.app.data_runtime.services.autopick_observation_ingest import (
    persist_autopick_observation_report_to_data_db,
)

TOP_N = 10

report = run_binance_auto_pick_observation(top_n=TOP_N)

out = persist_autopick_observation_report_to_data_db(report)

print({
    "top_n": TOP_N,
    "decision_status": report.decision_status,
    "selected_symbol": report.selected_symbol,
    "ranked_count": report.ranked_count,
    "candidate_count": out["candidate_count"],
    "data_persistence": out,
})
