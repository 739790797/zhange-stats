"""请求体上限中间件：Content-Length 预检、无长度流式计数、按路由模板放宽，超限 413 JSON。"""

from __future__ import annotations

import anyio
import httpx
from fastapi import FastAPI, File, Request, UploadFile
from pydantic import BaseModel

from app.core.body_limit import (
    DEFAULT_MAX_BODY_BYTES,
    BodyLimitMiddleware,
    too_large_detail,
)


class _Payload(BaseModel):
    text: str = ""


def _toy_app(*, default_max: int = 1024, rules=()) -> FastAPI:
    app = FastAPI()

    @app.post("/json")
    def post_json(body: _Payload) -> dict:
        return {"n": len(body.text)}

    @app.post("/raw")
    async def post_raw(request: Request) -> dict:
        return {"n": len(await request.body())}

    @app.post("/items/{item_id}/upload")
    async def post_upload(item_id: int, file: UploadFile = File(...)) -> dict:
        return {"n": len(await file.read()), "item": item_id}

    @app.get("/ping")
    def ping() -> dict:
        return {"ok": True}

    app.add_middleware(BodyLimitMiddleware, default_max=default_max, rules=rules)
    return app


def _request(app, method: str, path: str, **kwargs) -> httpx.Response:
    async def _call() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, **kwargs)

    return anyio.run(_call)


def _chunks(total: int, size: int = 256):
    async def gen():
        sent = 0
        while sent < total:
            step = min(size, total - sent)
            sent += step
            yield b"x" * step

    return gen()


def test_within_limit_passes() -> None:
    app = _toy_app()
    resp = _request(app, "POST", "/json", json={"text": "a" * 500})
    assert resp.status_code == 200
    assert resp.json() == {"n": 500}


def test_declared_length_over_limit_is_rejected_before_reading() -> None:
    app = _toy_app()
    sent: list[dict] = []

    async def receive():
        raise AssertionError("body must not be read")

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/json",
        "raw_path": b"/json",
        "query_string": b"",
        "root_path": "",
        "headers": [(b"content-type", b"application/json"), (b"content-length", b"999999999")],
        "client": ("127.0.0.1", 1),
        "server": ("test", 80),
    }
    anyio.run(app, scope, receive, send)
    assert sent[0]["status"] == 413
    assert (b"content-type", b"application/json") in sent[0]["headers"]
    assert sent[1]["body"].decode("utf-8") == '{"detail": "%s"}' % too_large_detail(1024)


def test_streamed_body_without_length_is_cut_off_with_413() -> None:
    app = _toy_app()
    for path in ("/json", "/raw"):
        resp = _request(
            app,
            "POST",
            path,
            content=_chunks(5000),
            headers={"content-type": "application/json"},
        )
        assert resp.status_code == 413, path
        assert resp.json() == {"detail": "请求体过大（上限 1KB）"}


def test_route_template_rule_raises_limit_only_for_that_route() -> None:
    app = _toy_app(rules=[("/items/{item_id}/upload", 64 * 1024)])
    files = {"file": ("a.bin", b"z" * 20_000, "application/octet-stream")}
    ok = _request(app, "POST", "/items/7/upload", files=files)
    assert ok.status_code == 200
    assert ok.json() == {"n": 20_000, "item": 7}

    too_big = _request(
        app, "POST", "/items/7/upload", files={"file": ("a.bin", b"z" * 70_000, "application/octet-stream")}
    )
    assert too_big.status_code == 413
    assert too_big.json()["detail"] == "请求体过大（上限 64KB）"

    other = _request(app, "POST", "/raw", content=b"y" * 20_000)
    assert other.status_code == 413


def test_get_and_non_http_scopes_unaffected() -> None:
    app = _toy_app()
    assert _request(app, "GET", "/ping").json() == {"ok": True}

    seen: list[str] = []

    async def inner(scope, receive, send):
        seen.append(scope["type"])

    mw = BodyLimitMiddleware(inner, default_max=1)
    anyio.run(mw, {"type": "lifespan"}, None, None)
    assert seen == ["lifespan"]


def test_rule_lookup() -> None:
    mw = BodyLimitMiddleware(
        lambda *a: None,
        rules=[("/api/a", 10), ("/api/members/{member_id}/avatar", 20)],
    )
    assert mw.rule_for("/api/a") == 10
    assert mw.rule_for("/api/a/") == 10
    assert mw.rule_for("/api/members/12/avatar") == 20
    assert mw.rule_for("/api/members/{member_id}/avatar") == 20
    assert mw.rule_for("/api/members/12/avatar/x") is None
    assert mw.rule_for("/api/b") is None
    assert mw.limit_for("/api/b") == DEFAULT_MAX_BODY_BYTES
    assert too_large_detail(8 * 1024 * 1024) == "请求体过大（上限 8MB）"
    assert too_large_detail(257 * 1024 * 1024 + 512 * 1024) == "请求体过大（上限 257.5MB）"
