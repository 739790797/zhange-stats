"""请求体上限（纯 ASGI）：先比 Content-Length，没有长度时边收边数；超限 413，不让 Starlette/uvicorn 把大包整份缓冲。"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable

from starlette.exceptions import HTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

DEFAULT_MAX_BODY_BYTES = 8 * 1024 * 1024
# multipart 边界、分段头与同表单里的小字段
MULTIPART_SLACK_BYTES = 1024 * 1024

_PARAM_SEGMENT = re.compile(r"\{[^/{}]+\}")


def _format_size(n: int) -> str:
    if n >= 1024 * 1024:
        mb = n / (1024 * 1024)
        return f"{mb:.0f}MB" if mb == int(mb) else f"{mb:.1f}MB"
    if n >= 1024:
        return f"{n // 1024}KB"
    return f"{n}B"


def too_large_detail(limit: int) -> str:
    return f"请求体过大（上限 {_format_size(limit)}）"


class RequestBodyTooLarge(HTTPException):
    """继承 Starlette HTTPException：FastAPI 读 body 时原样抛出，由 ExceptionMiddleware 回 413。"""

    def __init__(self, limit: int) -> None:
        super().__init__(status_code=413, detail=too_large_detail(limit))
        self.limit = limit


def _compile_template(template: str) -> re.Pattern[str]:
    segments = [
        "[^/]+" if _PARAM_SEGMENT.fullmatch(seg) else re.escape(seg)
        for seg in template.strip("/").split("/")
    ]
    return re.compile("^/" + "/".join(segments) + "/?$")


def _declared_length(scope: Scope) -> int | None:
    for key, value in scope.get("headers") or []:
        if key.lower() == b"content-length":
            try:
                return int(value)
            except ValueError:
                return None
    return None


async def _send_too_large(send: Send, limit: int) -> None:
    body = json.dumps({"detail": too_large_detail(limit)}, ensure_ascii=False).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


class BodyLimitMiddleware:
    """所有 HTTP 请求默认 DEFAULT_MAX_BODY_BYTES；rules 为 (路由模板, 上限)，模板段 `{x}` 匹配单段。"""

    def __init__(
        self,
        app: ASGIApp,
        *,
        default_max: int = DEFAULT_MAX_BODY_BYTES,
        rules: Iterable[tuple[str, int]] = (),
    ) -> None:
        self.app = app
        self.default_max = int(default_max)
        self._exact: dict[str, int] = {}
        self._patterns: list[tuple[re.Pattern[str], int]] = []
        for template, max_bytes in rules:
            if _PARAM_SEGMENT.search(template):
                self._patterns.append((_compile_template(template), int(max_bytes)))
            else:
                self._exact[template.rstrip("/") or "/"] = int(max_bytes)

    def rule_for(self, path: str) -> int | None:
        hit = self._exact.get(path.rstrip("/") or "/")
        if hit is not None:
            return hit
        for pattern, max_bytes in self._patterns:
            if pattern.match(path):
                return max_bytes
        return None

    def limit_for(self, path: str) -> int:
        hit = self.rule_for(path)
        return self.default_max if hit is None else hit

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        limit = self.limit_for(scope.get("path") or "/")
        declared = _declared_length(scope)
        if declared is not None and declared > limit:
            await _send_too_large(send, limit)
            return

        received = 0
        response_started = False

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body") or b"")
                if received > limit:
                    raise RequestBodyTooLarge(limit)
            return message

        async def tracking_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracking_send)
        except RequestBodyTooLarge as exc:
            if response_started:
                raise
            await _send_too_large(send, exc.limit)
