"""头像 / 酒馆附件 / Minecraft 上传：同步端点进线程池，只读上限 + 1 字节。"""

from __future__ import annotations

import inspect
import io

import pytest
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.testclient import TestClient
from starlette.datastructures import Headers

from app.api import articles as articles_api
from app.api.guides import minecraft_files as minecraft_files_api
from app.api.profile import avatar as avatar_api
from app.core.database import get_db
from app.core.deps import require_admin
from app.models.user import User, UserRole
from app.services import avatar_store
from app.services.articles import store as article_store
from app.services.minecraft import files as files_svc


class _CountingFile(io.BytesIO):
    def __init__(self, data: bytes) -> None:
        super().__init__(data)
        self.max_read = 0

    def read(self, size: int | None = -1) -> bytes:
        chunk = super().read(size)
        self.max_read = max(self.max_read, len(chunk))
        return chunk


def _upload(data: bytes, *, filename: str, content_type: str) -> tuple[UploadFile, _CountingFile]:
    raw = _CountingFile(data)
    return (
        UploadFile(file=raw, filename=filename, headers=Headers({"content-type": content_type})),
        raw,
    )


def _endpoint(router, path: str, method: str):
    for route in router.routes:
        if getattr(route, "path", None) == path and method in getattr(route, "methods", set()):
            return route.endpoint
    raise AssertionError(f"{method} {path} not found")


def test_upload_endpoints_are_plain_def() -> None:
    endpoints = [
        _endpoint(articles_api.router, "/articles/math/recognize", "POST"),
        _endpoint(articles_api.router, "/articles/assets", "POST"),
        _endpoint(avatar_api.router, "/profile/me/avatar", "POST"),
        _endpoint(avatar_api.router, "/members/{member_id}/avatar", "POST"),
        _endpoint(minecraft_files_api.router, "/files/upload", "POST"),
    ]
    assert not any(inspect.iscoroutinefunction(fn) for fn in endpoints)


def test_avatar_upload_reads_at_most_cap_plus_one() -> None:
    upload, raw = _upload(
        b"\x89PNG" + b"\x00" * (avatar_store.MAX_UPLOAD_BYTES + 4096),
        filename="big.png",
        content_type="image/png",
    )
    with pytest.raises(HTTPException) as exc:
        avatar_store.save_avatar_upload(1, upload, db=None, owner_user_id=None)
    assert exc.value.status_code == 400
    assert exc.value.detail == "头像不能超过 5MB"
    assert raw.max_read == avatar_store.MAX_UPLOAD_BYTES + 1


def test_article_asset_reads_at_most_attachment_cap_plus_one() -> None:
    upload, raw = _upload(
        b"%PDF-1.7\n" + b"0" * (article_store.MAX_ATTACHMENT_BYTES + 4096),
        filename="big.pdf",
        content_type="application/pdf",
    )
    with pytest.raises(HTTPException) as exc:
        article_store.save_article_asset(upload, db=None, owner_user_id=None)
    assert exc.value.detail == "附件不能超过 10MB"
    assert raw.max_read == article_store.MAX_ATTACHMENT_BYTES + 1


def test_article_image_reads_at_most_image_cap_plus_one() -> None:
    upload, raw = _upload(
        b"\x89PNG\r\n\x1a\n" + b"0" * (article_store.MAX_UPLOAD_BYTES + 4096),
        filename="big.png",
        content_type="image/png",
    )
    with pytest.raises(HTTPException) as exc:
        article_store.save_article_image(upload, db=None, owner_user_id=None)
    assert exc.value.detail == "图片不能超过 5MB"
    assert raw.max_read == article_store.MAX_UPLOAD_BYTES + 1


def test_minecraft_upload_route_reads_bounded(monkeypatch) -> None:
    monkeypatch.setattr("app.core.platform_deps.is_feature_enabled", lambda _db, _feature: True)
    monkeypatch.setattr(files_svc, "MAX_UPLOAD_BYTES", 10)
    seen: list[int] = []

    def fake_upload(_db, directory, filename, content):
        seen.append(len(content))
        return {"path": f"{directory}/{filename}", "name": filename}

    monkeypatch.setattr(files_svc, "upload_file", fake_upload)
    app = FastAPI()
    app.include_router(minecraft_files_api.router)
    app.dependency_overrides[get_db] = lambda: None
    app.dependency_overrides[require_admin] = lambda: User(
        id=1, username="admin", display_name="admin", password_hash="x", role=UserRole.admin
    )
    with TestClient(app) as client:
        resp = client.post(
            "/files/upload",
            data={"directory": "/mods"},
            files={"file": ("big.jar", b"x" * 100, "application/java-archive")},
        )
    assert resp.status_code == 200
    assert seen == [11]
