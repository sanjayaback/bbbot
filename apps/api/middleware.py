import time
import uuid
from fastapi import Request


async def request_id_middleware(request: Request, call_next):
    rid = request.headers.get("x-request-id") or str(uuid.uuid4())
    request.state.request_id = rid
    started=time.perf_counter()
    response = await call_next(request)
    response.headers["x-request-id"] = rid
    response.headers["x-content-type-options"] = "nosniff"
    response.headers["x-frame-options"] = "DENY"
    response.headers["referrer-policy"] = "no-referrer"
    response.headers["permissions-policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["x-response-time-ms"] = f"{(time.perf_counter()-started)*1000:.1f}"
    if request.url.path.startswith('/api/'):
        response.headers["cache-control"] = "no-store"
    return response
