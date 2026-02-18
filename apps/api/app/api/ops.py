from fastapi import APIRouter

router = APIRouter(prefix="/ops", tags=["ops"])

@router.get("/health")
def ops_health():
    return {"system_state": "OK", "note": "placeholder"}

