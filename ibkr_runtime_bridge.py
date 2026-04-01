from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ibkr_core_router import route

app = FastAPI()


@app.get("/health")
def health():
    return route("health")


@app.get("/ibkr/paper/account-status")
def account_status():
    result = route("status")
    return JSONResponse(status_code=200, content=result)


@app.post("/ibkr/paper/test-order")
async def test_order(request: Request):
    data = await request.json()
    result = route("order", data)
    return JSONResponse(status_code=200, content=result)
