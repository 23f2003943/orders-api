from fastapi import FastAPI, Header, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uuid
import time
import base64
from typing import Optional

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
catalog = [{"id": i} for i in range(1, TOTAL_ORDERS + 1)]

# Idempotency storage
idempotency_store = {}

# Rate limiting storage
rate_limit_store = {}


def check_rate_limit(client_id: str):
    now = time.time()

    history = rate_limit_store.get(client_id, [])

    # Keep only requests within the last 10 seconds
    history = [t for t in history if now - t < WINDOW]

    if len(history) >= RATE_LIMIT:
        retry_after = max(1, int(WINDOW - (now - history[0])) + 1)

        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded"},
            headers={"Retry-After": str(retry_after)}
        )

    history.append(now)
    rate_limit_store[client_id] = history

    return None


@app.post("/orders", status_code=201)
def create_order(
    payload: dict = Body(default={}),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    x_client_id: str = Header("default", alias="X-Client-Id")
):
    limited = check_rate_limit(x_client_id)
    if limited:
        return limited

    if idempotency_key in idempotency_store:
        return idempotency_store[idempotency_key]

    order = {
        "id": str(uuid.uuid4()),
        **payload
    }

    idempotency_store[idempotency_key] = order

    return order


@app.get("/orders")
def list_orders(
    limit: int = 10,
    cursor: Optional[str] = None,
    x_client_id: str = Header("default", alias="X-Client-Id")
):
    limited = check_rate_limit(x_client_id)
    if limited:
        return limited

    start = 0

    if cursor:
        try:
            start = int(base64.b64decode(cursor.encode()).decode())
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