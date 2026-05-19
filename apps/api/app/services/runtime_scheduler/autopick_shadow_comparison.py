from __future__ import annotations


def compare_autopick_shadow_reports(
    *,
    legacy_report,
    shadow_report,
) -> dict:
    fields: dict[str, dict[str, object]] = {}

    for name in (
        "decision_status",
        "selected_symbol",
        "selected_rank",
        "ranked_count",
    ):
        legacy_value = getattr(legacy_report, name, None)
        shadow_value = getattr(shadow_report, name, None)

        if legacy_value != shadow_value:
            fields[name] = {
                "legacy": legacy_value,
                "shadow": shadow_value,
            }

    return {
        "diverged": bool(fields),
        "fields": fields,
    }
