from apps.api.app.services.runtime_scheduler.autopick_tick_dependencies import (
    AutopickTickDependencies,
    build_autopick_tick_dependencies,
)


def test_autopick_tick_dependencies_contract():
    deps = AutopickTickDependencies(
        db=object(),
        settings=object(),
    )

    assert deps.db is not None
    assert deps.settings is not None


def test_build_autopick_tick_dependencies():
    deps = build_autopick_tick_dependencies(
        db="db",
        settings="settings",
    )

    assert deps.db == "db"
    assert deps.settings == "settings"
