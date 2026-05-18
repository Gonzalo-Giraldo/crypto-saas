from apps.api.app.services.runtime_scheduler.runtime_identity import (
    build_runtime_instance_id,
    build_runtime_owner_id,
)


def test_build_runtime_owner_id_is_stable():
    owner_a = build_runtime_owner_id(
        scheduler_name="auto_pick_internal",
    )

    owner_b = build_runtime_owner_id(
        scheduler_name="auto_pick_internal",
    )

    assert owner_a == owner_b

    assert owner_a == "auto_pick_internal-runtime"


def test_build_runtime_instance_id_is_unique():
    instance_a = build_runtime_instance_id(
        scheduler_name="auto_pick_internal",
    )

    instance_b = build_runtime_instance_id(
        scheduler_name="auto_pick_internal",
    )

    assert instance_a != instance_b


def test_build_runtime_instance_id_contains_scheduler_name():
    instance_id = build_runtime_instance_id(
        scheduler_name="auto_pick_internal",
    )

    assert "auto_pick_internal" in instance_id


def test_build_runtime_owner_id_requires_scheduler_name():
    try:
        build_runtime_owner_id(
            scheduler_name="",
        )
    except ValueError as exc:
        assert str(exc) == "scheduler_name_required"
    else:
        raise AssertionError("Expected scheduler_name_required")


def test_build_runtime_instance_id_requires_scheduler_name():
    try:
        build_runtime_instance_id(
            scheduler_name="",
        )
    except ValueError as exc:
        assert str(exc) == "scheduler_name_required"
    else:
        raise AssertionError("Expected scheduler_name_required")
