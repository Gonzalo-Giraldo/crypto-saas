from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class AuditOut(BaseModel):
    id: str
    user_id: Optional[str] = None
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    details: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AuditExportMetaOut(BaseModel):
    exported_at: str
    exported_by: str
    tenant_id: str
    limit: int
    from_iso: Optional[str] = None
    to_iso: Optional[str] = None
    records_count: int
    algorithm: str


class AuditExportOut(BaseModel):
    meta: AuditExportMetaOut
    records: list[AuditOut]
    payload_sha256: str
    signature_hmac_sha256: str
