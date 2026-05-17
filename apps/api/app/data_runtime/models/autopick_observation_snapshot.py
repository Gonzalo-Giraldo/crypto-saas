from sqlalchemy import Boolean, Column, DateTime, Float, Index, Integer, String, Text, func

from apps.api.app.data_runtime.session import DataBase


class AutopickObservationSnapshot(DataBase):
    """
    Append-only Auto-pick observation snapshot metadata.

    Data-plane only:
    - no runtime authority
    - no production DB foreign keys
    - no orders/fills/intents/risk references
    - no raw klines/ticker archives
    """

    __tablename__ = "autopick_observation_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_id = Column(String(64), unique=True, nullable=False)
    snapshot_hash = Column(String(64), nullable=False)

    broker = Column(String(16), nullable=False)
    market = Column(String(16), nullable=False)

    decision_status = Column(String(32), nullable=False)
    model_version = Column(String(64), nullable=False)

    selected_symbol = Column(String(32), nullable=True)
    selected_side = Column(String(16), nullable=True)
    selected_rank = Column(Integer, nullable=True)
    selected_score = Column(Float, nullable=True)
    selected_reason = Column(String(128), nullable=True)
    ranked_count = Column(Integer, nullable=False)
    partial_failure_count = Column(Integer, nullable=False)

    rejected_candidates_json = Column(Text, nullable=False, default="[]")

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_data_autopick_snapshot_hash", "snapshot_hash"),
        Index("ix_data_autopick_created_at", "created_at"),
        Index("ix_data_autopick_selected_symbol", "selected_symbol"),
        Index("ix_data_autopick_decision_status", "decision_status"),
    )



class AutopickObservationCandidate(DataBase):
    """
    Append-only Auto-pick ranked candidate observation.

    Data-plane only:
    - no runtime authority
    - no production DB foreign keys
    - no orders/fills/intents/risk references
    """

    __tablename__ = "autopick_observation_candidates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_id = Column(String(64), nullable=False)

    rank = Column(Integer, nullable=False)
    symbol = Column(String(32), nullable=True)
    side = Column(String(16), nullable=True)
    valid = Column(Boolean, nullable=False)
    reason = Column(String(128), nullable=True)
    final_score = Column(Float, nullable=True)
    selected = Column(Boolean, nullable=False)

    entry_price_reference = Column(Float, nullable=True)
    features_json = Column(Text, nullable=False, default="{}")

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_data_autopick_candidate_snapshot_id", "snapshot_id"),
        Index("ix_data_autopick_candidate_symbol", "symbol"),
        Index("ix_data_autopick_candidate_rank", "rank"),
        Index("ix_data_autopick_candidate_selected", "selected"),
        Index("ix_data_autopick_candidate_created_at", "created_at"),
    )



class AutopickObservationExport(DataBase):
    """
    Append-only Auto-pick export lifecycle record.

    Data-plane only:
    - tracks AWS DATA DB to local disk DATA DB export batches
    - gates purge by verification status
    - no runtime authority
    """

    __tablename__ = "autopick_observation_exports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    export_id = Column(String(64), unique=True, nullable=False)

    from_created_at = Column(DateTime(timezone=True), nullable=False)
    to_created_at = Column(DateTime(timezone=True), nullable=False)

    snapshot_count = Column(Integer, nullable=False)
    candidate_count = Column(Integer, nullable=False)

    destination_kind = Column(String(32), nullable=False)
    destination_path_or_uri = Column(String(512), nullable=False)
    checksum = Column(String(128), nullable=False)
    status = Column(String(32), nullable=False)

    started_at = Column(DateTime(timezone=True), nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    purged_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_data_autopick_export_id", "export_id"),
        Index("ix_data_autopick_export_status", "status"),
        Index("ix_data_autopick_export_window", "from_created_at", "to_created_at"),
    )
