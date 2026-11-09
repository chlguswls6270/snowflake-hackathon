"""Access control and bounded request bodies for the private demo APIs."""
import hashlib
import hmac
import os
import threading
import time
from collections import deque
from urllib.parse import urlparse

from fastapi import HTTPException, Request
from starlette.responses import JSONResponse

_requests = deque()
_lock = threading.Lock()


def require_access(request: Request):
    if not request.url.path.startswith("/api/"):
        return
    token = os.getenv("DEMO_ACCESS_TOKEN", "")
    local_demo = (
        os.getenv("ALLOW_LOCAL_DEMO") == "true"
        and request.client is not None
        and request.client.host in {"127.0.0.1", "::1"}
        and request.url.hostname in {"localhost", "127.0.0.1", "::1"}
        and not any(name in request.headers for name in
                    ("forwarded", "x-forwarded-for", "x-forwarded-host"))
        and (not request.headers.get("origin") or
             urlparse(request.headers["origin"]).hostname in {"localhost", "127.0.0.1", "::1"})
    )
    if not local_demo:
        if len(token) < 32:
            raise HTTPException(503, "이 기능은 현재 비활성화되어 있습니다.")
        supplied = request.headers.get("authorization", "").removeprefix("Bearer ")
        if not hmac.compare_digest(
            hashlib.sha256(supplied.encode()).digest(),
            hashlib.sha256(token.encode()).digest(),
        ):
            raise HTTPException(401, "접근 코드가 필요합니다.")
    # Shared cap per process; deploy with an upstream quota for multiple workers.
    now = time.monotonic()
    with _lock:
        while _requests and _requests[0] <= now - 60:
            _requests.popleft()
        if len(_requests) >= 20:
            raise HTTPException(429, "요청이 많습니다. 잠시 후 다시 시도해주세요.",
                                headers={"Retry-After": "60"})
        _requests.append(now)


class BodyLimitMiddleware:
    def __init__(self, app, max_bytes=65_536):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in {"POST", "PUT", "PATCH"}:
            return await self.app(scope, receive, send)
        chunks = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > self.max_bytes:
                response = JSONResponse({"detail": "요청 데이터가 너무 큽니다."}, status_code=413)
                return await response(scope, receive, send)
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        delivered = False

        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
            return await receive()

        await self.app(scope, bounded_receive, send)

