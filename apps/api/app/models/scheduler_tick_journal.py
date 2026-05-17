from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, func

from apps.api.app.db.session import Base


class SchedulerTickJournal(Base):
    __tablename__ = "scheduler_tick_journal"

    tick_id = Column(String, primary_key=True, nullable=False)
    scheduler_name = Column(String, index=True, nullable=False)

    started_at = Column(DateTime(timezone=True), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=False)
    duration_ms = Column(Integer, nullable=False)

    status = Column(String, index=True, nullable=False)
    overlap_blocked = Column(Boolean, nullable=False, default=False)
    runtime_locked = Column(Boolean, nullable=False, default=False)

    dry_run = Column(Boolean, nullable=False, default=True)
    trading_enabled = Column(Boolean, nullable=False, default=False)

    candidate_symbol = Column(String, nullable=True)
    candidate_score = Column(String, nullable=True)
    execution_mode = Column(String, nullable=True)

    decision_status = Column(String, nullable=True)
    selected_rank = Column(Integer, nullable=True)
    ranked_count = Column(Integer, nullable=True)
    top_n = Column(Integer, nullable=True)
    observation_payload_json = Column(Text, nullable=True)
    analytics_exported = Column(Boolean, nullable=False, default=False)

    mutation_attempted = Column(Boolean, nullable=False, default=False)
    mutation_executed = Column(Boolean, nullable=False, default=False)

    error = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
