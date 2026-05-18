from __future__ import annotations

import time
from datetime import datetime, timezone


class SchedulerTickRunner:
    def __init__(
        self,
        *,
        scheduler_name: str,
        db,
        on_success,
        on_failure,
    ):
        self.scheduler_name = scheduler_name
        self.db = db
        self.on_success = on_success
        self.on_failure = on_failure

    def run(self, fn, *, observer=None):
        started_monotonic = time.monotonic()
        started_at_wall = datetime.now(timezone.utc)

        try:
            result = observer(fn) if observer is not None else fn()

            duration_ms = int((time.monotonic() - started_monotonic) * 1000)

            self.on_success(
                db=self.db,
                scheduler_name=self.scheduler_name,
                started_at=started_at_wall,
                finished_at=datetime.now(timezone.utc),
                duration_ms=duration_ms,
                result=result,
            )

            return result

        except Exception as exc:
            duration_ms = int((time.monotonic() - started_monotonic) * 1000)

            self.on_failure(
                db=self.db,
                scheduler_name=self.scheduler_name,
                started_at=started_at_wall,
                finished_at=datetime.now(timezone.utc),
                duration_ms=duration_ms,
                error=exc,
            )

            raise


    def run_with_db_transaction(self, fn):
        try:
            result = self.run(fn)
            self.db.commit()
            return result
        except Exception:
            self.db.rollback()
            raise
