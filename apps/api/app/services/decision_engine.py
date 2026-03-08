def rank_scan_rows(
    rows: list[dict],
    *,
    include_blocked: bool,
    top_n: int,
) -> list[dict]:
    ranked = list(rows)
    ranked.sort(key=lambda r: (r["passed"], r["score"]), reverse=True)
    if not include_blocked:
        ranked = [r for r in ranked if bool(r.get("passed"))]
    return ranked[: max(1, int(top_n))]


def score_threshold_for_side(*, min_score_pct: float, side: str) -> float:
    normalized_side = str(side or "BUY").upper()
    if normalized_side == "SELL":
        return max(float(min_score_pct) + 4.0, 85.0)
    return float(min_score_pct)
