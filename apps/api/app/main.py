from fastapi import FastAPI
from apps.api.app.api.ops import router as ops_router

app = FastAPI(title="crypto-saas API")

app.include_router(ops_router)

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

