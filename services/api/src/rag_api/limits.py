"""Bound total multipart bytes before unbounded request spooling."""

from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class BodyLimit:
    def __init__(self, app: ASGIApp, limit: int) -> None:
        self.app, self.limit = app, limit

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers", []))
        try:
            length = int(headers.get(b"content-length", b"0"))
        except ValueError:
            length = self.limit + 1
        response = JSONResponse(
            status_code=413,
            content={
                "code": "upload_too_large",
                "message": "The request exceeds the upload limit.",
                "retryable": False,
            },
        )
        if length > self.limit:
            await response(scope, receive, send)
            return
        count = 0

        async def bounded_receive() -> Message:
            nonlocal count
            message = await receive()
            count += len(message.get("body", b""))
            if count > self.limit:
                raise HTTPException(413, "The request exceeds the upload limit.")
            return message

        await self.app(scope, bounded_receive, send)
