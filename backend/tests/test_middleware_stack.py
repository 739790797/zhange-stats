"""app.main 中间件栈：顺序、向导 503 带 CORS 且被记日志、请求体上限接线、上传目录静态文件。"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

import anyio
import httpx
import pytest
from starlette.applications import Starlette
from starlette.routing import Mount

from app.core import setup_middleware
from app.core.body_limit import BodyLimitMiddleware
from app.core.config import get_settings
from app.core.http_headers import CSP_POLICY, SecurityHeadersMiddleware
from app.main import BODY_LIMIT_RULES, UPLOAD_CSP, UploadStaticFiles, app

ORIGIN = "http://localhost:5173"


def _call(target, method: str, path: str, **kwargs) -> httpx.Response:
    async def _run() -> httpx.Response:
        transport = httpx.ASGITransport(app=target)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, **kwargs)

    return anyio.run(_run)


@pytest.fixture
def setup_pending(monkeypatch):
    monkeypatch.setattr(setup_middleware, "is_setup_complete_cached", lambda: False)
    monkeypatch.setattr(setup_middleware, "_peek_setup_required", lambda: True)


@pytest.fixture
def setup_done(monkeypatch):
    monkeypatch.setattr(setup_middleware, "is_setup_complete_cached", lambda: True)


def test_middleware_order_outer_to_inner() -> None:
    names = [m.cls.__name__ for m in app.user_middleware]
    assert names == [
        "SecurityHeadersMiddleware",
        "RequestLogMiddleware",
        "GZipMiddleware",
        "CORSMiddleware",
        "SetupRequiredMiddleware",
        "BodyLimitMiddleware",
    ]


def test_setup_503_carries_cors_and_is_logged(setup_pending, caplog) -> None:
    with caplog.at_level(logging.INFO, logger="zhange.http"):
        resp = _call(app, "GET", "/api/members", headers={"Origin": ORIGIN})
    assert resp.status_code == 503
    assert resp.json()["code"] == "SETUP_REQUIRED"
    assert resp.headers.get("access-control-allow-origin") == ORIGIN
    assert resp.headers.get("access-control-allow-credentials") == "true"
    assert resp.headers.get("x-content-type-options") == "nosniff"
    msgs = [r.getMessage() for r in caplog.records if r.name == "zhange.http"]
    assert any(m.startswith("GET /api/members -> 503") for m in msgs)


def test_cors_preflight_answered_during_setup_and_logged(setup_pending, caplog) -> None:
    with caplog.at_level(logging.INFO, logger="zhange.http"):
        resp = _call(
            app,
            "OPTIONS",
            "/api/members",
            headers={"Origin": ORIGIN, "Access-Control-Request-Method": "POST"},
        )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == ORIGIN
    msgs = [r.getMessage() for r in caplog.records if r.name == "zhange.http"]
    assert any(m.startswith("OPTIONS /api/members -> 200") for m in msgs)


def test_every_upload_route_has_explicit_body_limit() -> None:
    limiter = BodyLimitMiddleware(lambda *a: None, rules=BODY_LIMIT_RULES)
    spec = app.openapi()
    uploads = [
        path
        for path, ops in spec["paths"].items()
        for op in ops.values()
        if "multipart/form-data" in ((op.get("requestBody") or {}).get("content") or {})
    ]
    assert len(uploads) >= 8
    missing = [p for p in uploads if limiter.rule_for(p) is None]
    assert missing == []
    assert limiter.limit_for("/api/settings/files/upload") > 256 * 1024 * 1024
    assert limiter.limit_for("/api/guides/minecraft/files/upload") > 64 * 1024 * 1024
    assert limiter.limit_for("/api/members/3/avatar") < limiter.default_max


def test_csp_report_and_client_rum_are_capped(setup_done) -> None:
    ok = _call(
        app,
        "POST",
        "/api/csp-report",
        content=b'{"csp-report":{"blocked-uri":"https://evil.example/x"}}',
        headers={"content-type": "application/csp-report"},
    )
    assert ok.status_code == 200
    assert ok.json() == {"ok": True}

    big = _call(
        app,
        "POST",
        "/api/csp-report",
        content=b"{" + b" " * (70 * 1024) + b"}",
        headers={"content-type": "application/csp-report"},
    )
    assert big.status_code == 413
    assert big.json() == {"detail": "请求体过大（上限 64KB）"}

    async def chunks():
        for _ in range(80):
            yield b" " * 1024

    streamed = _call(
        app,
        "POST",
        "/api/csp-report",
        content=chunks(),
        headers={"content-type": "application/csp-report"},
    )
    assert streamed.status_code == 413

    rum = _call(app, "POST", "/api/client-rum", content=b" " * (300 * 1024), headers={"content-type": "application/json"})
    assert rum.status_code == 413


def _raw_post(path: str, content_length: int) -> list[dict]:
    sent: list[dict] = []
    reads = {"n": 0}

    async def receive():
        reads["n"] += 1
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": [
            (b"host", b"test"),
            (b"content-type", b"multipart/form-data; boundary=x"),
            (b"content-length", str(content_length).encode()),
        ],
        "client": ("127.0.0.1", 1),
        "server": ("test", 80),
    }
    anyio.run(app, scope, receive, send)
    sent.append({"type": "reads", "n": reads["n"]})
    return sent


def test_upload_rule_applies_through_the_app(setup_done) -> None:
    rejected = _raw_post("/api/settings/files/upload", 300 * 1024 * 1024)
    assert rejected[0]["status"] == 413
    assert rejected[-1]["n"] == 0

    passed = _raw_post("/api/settings/files/upload", 9 * 1024 * 1024)
    assert passed[0]["status"] != 413

    default_capped = _raw_post("/api/members/3/avatar", 7 * 1024 * 1024)
    assert default_capped[0]["status"] == 413


def test_upload_mounts_use_upload_static_files() -> None:
    mounts = {r.path: r.app for r in app.routes if isinstance(r, Mount)}
    avatars = mounts["/uploads/avatars"]
    articles = mounts["/uploads/articles"]
    assert isinstance(avatars, UploadStaticFiles)
    assert isinstance(articles, UploadStaticFiles)
    assert avatars._cache_control == "public, max-age=86400"
    assert articles._cache_control == "public, max-age=604800"


def _upload_app(directory: Path) -> Starlette:
    inner = Starlette(
        routes=[Mount("/uploads/articles", UploadStaticFiles(directory, cache_control="public, max-age=60"))]
    )
    return SecurityHeadersMiddleware(inner)


def test_upload_static_files_headers_and_active_types(tmp_path: Path) -> None:
    root = tmp_path / "articles"
    root.mkdir()
    (root / "a.png").write_bytes(b"\x89PNG\r\n\x1a\nfake")
    (root / "doc.lml").write_text("<script>alert(1)</script>", encoding="utf-8")
    for name in ("x.html", "x.htm", "x.svg", "x.xml", "x.js", "x.xhtml", "X.SVG"):
        (root / name).write_text("<svg onload=alert(1)>", encoding="utf-8")
    target = _upload_app(root)

    png = _call(target, "GET", "/uploads/articles/a.png")
    assert png.status_code == 200
    assert png.headers["content-type"] == "image/png"
    assert png.headers["cache-control"] == "public, max-age=60"
    assert png.headers["x-content-type-options"] == "nosniff"
    assert png.headers["content-security-policy"] == UPLOAD_CSP

    etag = png.headers["etag"]
    cached = _call(target, "GET", "/uploads/articles/a.png", headers={"If-None-Match": etag})
    assert cached.status_code == 304
    assert cached.headers["cache-control"] == "public, max-age=60"

    lml = _call(target, "GET", "/uploads/articles/doc.lml")
    assert lml.status_code == 200
    assert lml.headers["content-type"] == "application/octet-stream"
    assert lml.headers["x-content-type-options"] == "nosniff"
    assert lml.headers["content-security-policy"] == UPLOAD_CSP

    for name in ("x.html", "x.htm", "x.svg", "x.xml", "x.js", "x.xhtml", "X.SVG"):
        resp = _call(target, "GET", f"/uploads/articles/{name}")
        assert resp.status_code == 404, name


@pytest.mark.parametrize("enforce", [False, True])
def test_upload_csp_is_the_only_policy_and_images_keep_their_type(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, enforce: bool
) -> None:
    monkeypatch.setenv("CSP_ENFORCE", "true" if enforce else "false")
    get_settings.cache_clear()
    root = tmp_path / "articles"
    root.mkdir()
    images = {
        "a.jpg": (b"\xff\xd8\xff\xe0fake", "image/jpeg"),
        "a.png": (b"\x89PNG\r\n\x1a\nfake", "image/png"),
        "a.gif": (b"GIF89afake", "image/gif"),
        "a.webp": (b"RIFF\x00\x00\x00\x00WEBPfake", "image/webp"),
        "a.pdf": (b"%PDF-1.4 fake", "application/pdf"),
    }
    for name, (raw, _) in images.items():
        (root / name).write_bytes(raw)
    target = _upload_app(root)

    for name, (raw, media_type) in images.items():
        resp = _call(target, "GET", f"/uploads/articles/{name}")
        assert resp.status_code == 200, name
        assert resp.headers["content-type"] == media_type, name
        assert resp.content == raw, name
        assert resp.headers["content-security-policy"] == UPLOAD_CSP, name
        assert "content-security-policy-report-only" not in resp.headers, name

    site = _call(app, "GET", "/robots.txt")
    site_header = "content-security-policy" if enforce else "content-security-policy-report-only"
    assert site.headers[site_header] == CSP_POLICY


def test_upload_static_files_missing_directory_is_404(tmp_path: Path) -> None:
    target = _upload_app(tmp_path / "not-created-yet")
    resp = _call(target, "GET", "/uploads/articles/a.png")
    assert resp.status_code == 404
    assert not (tmp_path / "not-created-yet").exists()


def test_importing_app_and_building_openapi_writes_nothing(tmp_path: Path) -> None:
    install = tmp_path / "install"
    install.mkdir()
    (install / "VERSION").write_text("0.0.0\n", encoding="utf-8")
    (install / "backend").mkdir()
    env = {**os.environ, "APP_INSTALL_DIR": str(install)}
    for name in ("DATABASE_URL", "SECRET_KEY", "DATA_DIR", "UPLOAD_DIR"):
        env.pop(name, None)
    backend = Path(__file__).resolve().parents[1]
    proc = subprocess.run(
        [sys.executable, "-c", "from app.main import app; app.openapi()"],
        cwd=backend,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert sorted(p.name for p in install.iterdir()) == ["VERSION", "backend"]
