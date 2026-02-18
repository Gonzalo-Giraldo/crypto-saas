from fastapi import FastAPI
from apps.api.app.api.ops import router as ops_router
from apps.api.app.api.users import router as users_router
from apps.api.app.db.session import engine, Base
from apps.api.app.models import User  # asegura import para metadata

app = FastAPI(title="crypto-saas API")

Base.metadata.create_all(bind=engine)

app.include_router(ops_router)
app.include_router(users_router)

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

