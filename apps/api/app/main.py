from apps.api.app.api.signals import router as signals_router
from apps.api.app.api.positions import router as positions_router
from apps.api.app.routes.auth import router as auth_router

import apps.api.app.models.signal
import apps.api.app.models.position
import apps.api.app.models.daily_risk
import apps.api.app.models.user_2fa
import apps.api.app.models.audit_log
import apps.api.app.models.exchange_secret
import apps.api.app.models.strategy_assignment
import apps.api.app.models.user_risk_profile
import apps.api.app.models.revoked_token
import apps.api.app.models.session_revocation
import apps.api.app.models.runtime_setting
import apps.api.app.models.idempotency_key

from fastapi import FastAPI

from apps.api.app.api.ops import router as ops_router
from apps.api.app.api.users import router as users_router

from apps.api.app.db.session import engine, Base

app = FastAPI(title="crypto-saas API")

# OJO: users_router ya importa el modelo User, así que el modelo ya queda registrado.
Base.metadata.create_all(bind=engine)

app.include_router(ops_router)
app.include_router(users_router)
app.include_router(signals_router)
app.include_router(positions_router)

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

@app.get("/")
def root():
    return {"app": "crypto-saas", "docs": "/docs"}

app.include_router(auth_router)
