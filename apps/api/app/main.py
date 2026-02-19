from apps.api.app.api.signals import router as signals_router

import apps.api.app.models.signal

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

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

@app.get("/")
def root():
    return {"app": "crypto-saas", "docs": "/docs"}


