from apps.api.app.services.risk.post_fill_exit_timing import (
    should_build_authoritative_post_fill_plan,
)


def test_matched_allows_authoritative_post_fill_plan():
    assert (
        should_build_authoritative_post_fill_plan(
            reconciliation_status="matched",
        )
        is True
    )


def test_partial_blocks_authoritative_post_fill_plan():
    assert (
        should_build_authoritative_post_fill_plan(
            reconciliation_status="partial",
        )
        is False
    )


def test_overfilled_blocks_authoritative_post_fill_plan():
    assert (
        should_build_authoritative_post_fill_plan(
            reconciliation_status="overfilled",
        )
        is False
    )


def test_missing_blocks_authoritative_post_fill_plan():
    assert (
        should_build_authoritative_post_fill_plan(
            reconciliation_status="missing",
        )
        is False
    )


def test_invalid_blocks_authoritative_post_fill_plan():
    assert (
        should_build_authoritative_post_fill_plan(
            reconciliation_status="invalid",
        )
        is False
    )


def test_empty_blocks_authoritative_post_fill_plan():
    assert (
        should_build_authoritative_post_fill_plan(
            reconciliation_status="",
        )
        is False
    )
