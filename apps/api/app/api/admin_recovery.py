from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from apps.api.app.core.config import settings
from apps.api.app.db.session import get_db
from apps.api.app.models.user import User
from apps.api.app.api.users import reset_user_2fa

router = APIRouter(tags=["admin-recovery"])

_ALLOWED_EMAIL = "gonzalogiraldo@yahoo.com"


def _guard(
    x_recovery_token: str | None = Header(default=None, alias="X-RECOVERY-TOKEN"),
):
    if not settings.ADMIN_RECOVERY_ENABLED:
        raise HTTPException(status_code=404, detail="Not found")

    expected = (settings.ADMIN_RECOVERY_TOKEN or "").strip()
    provided = (x_recovery_token or "").strip()

    if not expected or provided != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid recovery token")


@router.post("/admin-recovery/2fa/reset")
def admin_recovery_reset(
    email: str = Query(...),
    _: None = Depends(_guard),
    db: Session = Depends(get_db),
):
    normalized = email.strip().lower()

    if normalized != _ALLOWED_EMAIL:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    user = db.query(User).filter(User.email == normalized).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return reset_user_2fa(
        user_id=user.id,
        reason="admin_recovery",
        db=db,
        current_user=user,
    )
