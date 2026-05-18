from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, func

from apps.api.app.db.session import Base


class SchedulerRuntimeState(Base):
    __tablename__ = "scheduler_runtime_state"

    scheduler_name = Column(String, primary_key=True, nullable=False)

    last_tick_at = Column(DateTime(timezone=True), nullable=True)
    last_tick_status = Column(String, nullable=False, default="UNKNOWN")
    last_tick_duration_ms = Column(Integer, nullable=True)
    last_error = Column(Text, nullable=True)

    overlap_blocked = Column(Boolean, nullable=False, default=False)
    runtime_locked = Column(Boolean, nullable=False, default=False)

    dry_run = Column(Boolean, nullable=False, default=True)
    trading_enabled = Column(Boolean, nullable=False, default=False)

    last_candidate_symbol = Column(String, nullable=True)
    last_candidate_score = Column(String, nullable=True)
    last_execution_mode = Column(String, nullable=True)

    runtime_owner_id = Column(String, nullable=True)
    runtime_instance_id = Column(String, nullable=True)
    runtime_generation = Column(Integer, nullable=True)
    last_runtime_generation = Column(Integer, nullable=False, default=0, server_default="0")

    runtime_started_at = Column(DateTime(timezone=True), nullable=True)
    runtime_heartbeat_at = Column(DateTime(timezone=True), nullable=True)

    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
