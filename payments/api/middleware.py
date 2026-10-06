"""Request logging.

A plain ASGI middleware rather than ``BaseHTTPMiddleware`` so the request id
it sets is visible to handlers running in the threadpool.
"""

from payments.clock import Clock
from payments.ids import Ids
from payments.log import EventLogger, request_id_var


class RequestLogMiddleware:
    def __init__(self, app, *, log: EventLogger, ids: Ids, clock: Clock) -> None:
        self.app = app
        self._log = log
        self._ids = ids
        self._clock = clock

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope["headers"]}
        request_id = headers.get("x-request-id") or self._ids.new("req")
        token = request_id_var.set(request_id)
        started = self._clock.now()
        status = 500
        self._log.info(
            "http.request",
            method=scope["method"],
            path=scope["path"],
            idempotency_key=headers.get("idempotency-key"),
        )

        async def send_with_request_id(message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                extra = [(b"x-request-id", request_id.encode("latin-1"))]
                message = {**message, "headers": [*message.get("headers", []), *extra]}
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            duration_ms = int((self._clock.now() - started).total_seconds() * 1000)
            emit = self._log.warning if status >= 500 else self._log.info
            emit(
                "http.response",
                method=scope["method"],
                path=scope["path"],
                status=status,
                duration_ms=duration_ms,
            )
            request_id_var.reset(token)
