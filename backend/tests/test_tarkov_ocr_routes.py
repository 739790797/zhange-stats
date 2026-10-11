"""塔科夫截图识别路由：普通 def（线程池），先占识别槽再解图；流式进度由工作线程还槽。"""

from __future__ import annotations

import inspect
import io
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from app.api.guides import tarkov as tarkov_api
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User, UserRole
from app.services.ocr.types import NamedEngine
from app.services.tarkov import key_ocr as key_ocr_svc
from app.services.tarkov import raid_prep_ocr as raid_prep_ocr_svc


def _png(width: int, height: int) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (40, 40, 40)).save(buf, format="PNG")
    return buf.getvalue()


def _upload(raw: bytes) -> dict:
    return {"file": ("shot.png", raw, "image/png")}


class _Engine:
    def recognize(self, image):
        return []


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr("app.core.platform_deps.is_feature_enabled", lambda _db, _feature: True)
    monkeypatch.setattr(tarkov_api.platform_limiter, "hit", lambda *_a, **_k: None)
    app = FastAPI()
    app.include_router(tarkov_api.router)
    app.dependency_overrides[get_db] = lambda: None
    app.dependency_overrides[get_current_user] = lambda: User(
        id=7, username="u7", display_name="七", password_hash="x", role=UserRole.user
    )
    with TestClient(app) as tc:
        yield tc


@pytest.fixture
def key_catalog(monkeypatch):
    monkeypatch.setattr(tarkov_api.key_packs_svc, "list_key_packs", lambda _db: {})
    monkeypatch.setattr(
        key_ocr_svc,
        "resolve_recognizers",
        lambda **_k: [NamedEngine(name="fake", engine=_Engine())],
    )


def _slot_free() -> bool:
    if not key_ocr_svc.try_begin_recognize():
        return False
    key_ocr_svc.end_recognize()
    return True


def test_recognize_routes_run_in_threadpool() -> None:
    endpoints = {
        route.path: route.endpoint
        for route in tarkov_api.router.routes
        if getattr(route, "path", "").endswith("/recognize")
    }
    assert set(endpoints) == {"/tarkov/key-owns/recognize", "/tarkov/raid-prep/recognize"}
    assert not any(inspect.iscoroutinefunction(fn) for fn in endpoints.values())


def test_busy_slot_rejects_before_decoding(client, key_catalog, monkeypatch) -> None:
    decoded: list[int] = []
    monkeypatch.setattr(key_ocr_svc, "load_image", lambda raw: decoded.append(len(raw)))
    assert key_ocr_svc.try_begin_recognize()
    try:
        resp = client.post("/tarkov/key-owns/recognize", files=_upload(_png(200, 200)))
    finally:
        key_ocr_svc.end_recognize()
    assert resp.status_code == 429
    assert resp.json()["detail"] == "已有识别任务在运行，请稍后再试"
    assert decoded == []


def test_unreadable_screenshot_is_400_and_frees_slot(client, key_catalog) -> None:
    resp = client.post("/tarkov/key-owns/recognize", files=_upload(b"not-an-image"))
    assert resp.status_code == 400
    assert resp.json()["detail"] == "无法读取截图"
    assert _slot_free()


def test_inline_recognize_returns_result_and_frees_slot(client, key_catalog, monkeypatch) -> None:
    def fake_recognize(image, catalog, *, recognizers=None, **_k):
        assert not _slot_free()
        return {"matches": [], "tile_count": 1, "engines": [rec.name for rec in recognizers]}

    monkeypatch.setattr(key_ocr_svc, "recognize_image", fake_recognize)
    resp = client.post("/tarkov/key-owns/recognize", files=_upload(_png(200, 200)))
    assert resp.status_code == 200
    assert resp.json()["engines"] == ["fake"]
    assert _slot_free()


def test_stream_hands_slot_to_worker_until_done(client, key_catalog, monkeypatch) -> None:
    def fake_recognize(image, catalog, *, recognizers=None, progress=None, cancel=None, **_k):
        progress("切块识别中", {"phase": "ocr", "percent": 40})
        return {"matches": [], "tile_count": 2, "engines": ["fake"]}

    monkeypatch.setattr(key_ocr_svc, "recognize_image", fake_recognize)
    resp = client.post(
        "/tarkov/key-owns/recognize",
        files=_upload(_png(200, 200)),
        headers={"accept": "application/x-ndjson"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/x-ndjson")
    events = [json.loads(line) for line in resp.text.splitlines() if line.strip()]
    assert [row["event"] for row in events] == ["progress", "done"]
    assert events[0]["percent"] == 40
    assert events[1]["result"]["tile_count"] == 2
    assert _slot_free()


def test_stream_reports_worker_errors_as_events(client, key_catalog, monkeypatch) -> None:
    def boom(*_a, **_k):
        raise RuntimeError("engine crashed")

    monkeypatch.setattr(key_ocr_svc, "recognize_image", boom)
    resp = client.post(
        "/tarkov/key-owns/recognize",
        files=_upload(_png(200, 200)),
        headers={"x-recognize-progress": "1"},
    )
    events = [json.loads(line) for line in resp.text.splitlines() if line.strip()]
    assert events == [{"event": "error", "status_code": 500, "detail": "识别失败，请重试"}]
    assert _slot_free()


def test_raid_prep_busy_slot_skips_catalog_and_decode(client, monkeypatch) -> None:
    touched: list[str] = []
    monkeypatch.setattr(tarkov_api.tasks_svc, "ensure_tasks", lambda _db: touched.append("ensure"))
    assert raid_prep_ocr_svc.try_begin_recognize()
    try:
        resp = client.post(
            "/tarkov/raid-prep/recognize",
            params={"map": "customs"},
            files=_upload(_png(320, 180)),
        )
    finally:
        raid_prep_ocr_svc.end_recognize()
    assert resp.status_code == 429
    assert touched == []


def test_raid_prep_narrow_shot_returns_empty_and_frees_slot(client, monkeypatch) -> None:
    monkeypatch.setattr(tarkov_api.tasks_svc, "ensure_tasks", lambda _db: None)
    monkeypatch.setattr(tarkov_api.tasks_svc, "list_raid_prep", lambda _db, _slug: {"items": []})
    resp = client.post(
        "/tarkov/raid-prep/recognize",
        params={"map": "customs"},
        files=_upload(_png(200, 200)),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["widescreen"] is False
    assert body["matches"] == []
    assert _slot_free()
