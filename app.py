from fastapi import FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi import Body
from typing import Optional
import uuid
import time
import base64

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TOTAL_ORDERS = 45
RATE_LIMIT = 16
WINDOW = 10

# Fixed catalog
catalog = [
    {
        "id": i,
        "item": f"Item {i}"
    }
    for i in range(1, TOTAL_ORDERS + 1)
]

# Idempotency storage
idempotency_store = {}

# Rate limiting storage
rate_limit_store = {}


class OrderRequest(BaseModel):
    item: str


def check_rate_limit(client_id: str, response: Response):
    now = time.time()

    history = rate_limit_store.get(client_id, [])

    history = [t for t in history if now - t < WINDOW]

    if len(history) >= RATE_LIMIT:
        retry_after = WINDOW - (now - history[0])
        response.headers["Retry-After"] = str(int(retry_after) + 1)
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    history.append(now)

    rate_limit_store[client_id] = history


@app.post("/orders", status_code=201)
def create_order(
    response: Response,
    payload: dict = Body(default={}),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    x_client_id: str = Header("default", alias="X-Client-Id")
):
    check_rate_limit(x_client_id, response)

    if idempotency_key in idempotency_store:
        return idempotency_store[idempotency_key]

    new_order = {
        "id": str(uuid.uuid4()),
        **payload
    }

    idempotency_store[idempotency_key] = new_order
    return new_order


@app.get("/orders")
def list_orders(
    response: Response,
    limit: int = 10,
    cursor: Optional[str] = None,
    x_client_id: str = Header("default", alias="X-Client-Id")
):

    check_rate_limit(x_client_id, response)

    start = 0

    if cursor:
        try:
            start = int(base64.b64decode(cursor).decode())
        except Exception:
            start = 0

    end = min(start + limit, TOTAL_ORDERS)

    items = catalog[start:end]

    next_cursor = None

    if end < TOTAL_ORDERS:
        next_cursor = base64.b64encode(str(end).encode()).decode()

    return {
        "items": items,
        "next_cursor": next_cursor
    }