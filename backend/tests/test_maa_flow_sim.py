"""模拟 MAA 全托管控制面 + Worker 回调（无 Docker / Redroid）。"""

from __future__ import annotations

import io
from contextlib import asynccontextmanager
from pathlib import Path

import anyio
import httpx
import pytest
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.maa import MaaJob, MaaSlot, MaaSlotAudit  # noqa: F401
from app.models.member import Member
from app.models.system_config import SystemConfig  # noqa: F401
from app.models.user import User, UserRole
from app.services.platform_features import (
    default_features,
    invalidate_feature_cache,
    save_feature_flags,
)


@asynccontextmanager
async def _noop_lifespan(_app):
    """跳过生产 lifespan（migrate / MySQL），本套件自建 sqlite。"""
    yield


@pytest.fixture()
def maa_env(tmp_path, monkeypatch):
    monkeypatch.setenv("MAA_WORKER_TOKEN", "test-worker-token")
    monkeypatch.setenv("MAA_MAX_SLOTS", "2")
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)

    from app.core.config import get_settings

    get_settings.cache_clear()

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = Session()

    admin = User(
        username="maa_admin",
        email="maa_admin@example.com",
        password_hash=hash_password("Str0ng-Enough!"),
        role=UserRole.admin,
        email_verified=True,
        display_name="MAA Admin",
    )
    user = User(
        username="maa_user",
        email="maa_user@example.com",
        password_hash=hash_password("Str0ng-Enough!"),
        role=UserRole.user,
        email_verified=True,
        display_name="MAA User",
    )
    db.add_all([admin, user])
    db.flush()
    member = Member(nickname="test-op", user_id=user.id)
    db.add(member)
    db.commit()
    db.refresh(admin)
    db.refresh(user)
    db.refresh(member)

    flags = default_features()
    flags["skland"] = True
    flags["skland.arknights"] = True
    flags["skland.arknights.maa"] = True
    save_feature_flags(db, flags)
    invalidate_feature_cache()

    def _override():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    # httpx 旧版无 lifespan= 参数；直接替换路由 lifespan，避免 CI 连 MySQL
    prev_lifespan = app.router.lifespan_context
    app.router.lifespan_context = _noop_lifespan

    yield {
        "db": db,
        "admin_headers": {
            "Authorization": f"Bearer {create_access_token(admin.username)}"
        },
        "user_headers": {
            "Authorization": f"Bearer {create_access_token(user.username)}"
        },
        "worker_headers": {"X-Maa-Worker-Token": "test-worker-token"},
        "member_id": member.id,
        "data_dir": Path(tmp_path / "data"),
    }

    app.router.lifespan_context = prev_lifespan
    app.dependency_overrides.clear()
    db.close()
    engine.dispose()
    get_settings.cache_clear()
    invalidate_feature_cache()


def _jpeg_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (1280, 720), color=(30, 144, 255)).save(buf, format="JPEG")
    return buf.getvalue()


def test_maa_full_lifecycle_simulation(maa_env):
    ah = maa_env["admin_headers"]
    uh = maa_env["user_headers"]
    wh = maa_env["worker_headers"]
    member_id = maa_env["member_id"]
    data_dir = maa_env["data_dir"]

    async def _run() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as c:
            r = await c.get("/api/settings/maa", headers=ah)
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["summary"]["max_slots"] == 2
            assert body["summary"]["active_slots"] == 0

            r = await c.post("/api/settings/maa/slots", headers=ah)
            assert r.status_code == 200, r.text
            slot = r.json()
            slot_id = slot["id"]
            assert slot["status"] == "provisioning"
            assert slot["desired_action"] == "provision"

            r = await c.get("/api/internal/maa/pull", headers=wh)
            assert r.status_code == 200, r.text
            assert any(s["id"] == slot_id for s in r.json()["slots"])

            r = await c.post(
                "/api/internal/maa/heartbeat",
                headers=wh,
                json={
                    "slot_id": slot_id,
                    "status": "online",
                    "clear_desired_action": True,
                    "container_name": f"zhange-maa-slot-{slot_id}",
                    "volume_name": f"zhange-maa-slot-{slot_id}-data",
                    "adb_endpoint": f"zhange-maa-slot-{slot_id}:5555",
                    "last_error": "",
                    "audit_action": "provision_ready",
                    "audit_message": "sim provision ready",
                    "audit_result": "success",
                },
            )
            assert r.status_code == 200, r.text
            assert r.json()["status"] == "online"

            # 已就绪时可直接绑定；无需再 start
            r = await c.post(
                f"/api/settings/maa/slots/{slot_id}/bind",
                headers=ah,
                json={"member_id": member_id},
            )
            assert r.status_code == 200, r.text
            assert r.json()["bound_member_id"] == member_id

            r = await c.get("/api/maa/me", headers=uh)
            assert r.status_code == 200, r.text
            assert r.json()["assigned"] is True

            r = await c.post("/api/maa/me/daily", headers=uh)
            assert r.status_code == 200, r.text
            job_id = r.json()["id"]

            r = await c.post(
                "/api/internal/maa/jobs/update",
                headers=wh,
                json={"job_id": job_id, "status": "running"},
            )
            assert r.status_code == 200

            rel = f"maa/{slot_id}/latest.jpg"
            shot_path = data_dir / rel
            shot_path.parent.mkdir(parents=True, exist_ok=True)
            shot_path.write_bytes(_jpeg_bytes())

            r = await c.post(
                "/api/internal/maa/heartbeat",
                headers=wh,
                json={
                    "slot_id": slot_id,
                    "screenshot_relpath": rel.replace("\\", "/"),
                    "cpu_percent": "40.0",
                    "memory_usage_mb": "800.0",
                },
            )
            assert r.status_code == 200
            assert r.json()["has_screenshot"] is True

            r = await c.post(
                "/api/internal/maa/jobs/update",
                headers=wh,
                json={"job_id": job_id, "status": "success"},
            )
            assert r.status_code == 200

            r = await c.get("/api/maa/me/screenshot", headers=uh)
            assert r.status_code == 200
            assert len(r.content) > 100

            r = await c.get(f"/api/settings/maa/slots/{slot_id}/audits", headers=ah)
            assert r.status_code == 200
            actions = {a["action"] for a in r.json()}
            assert "create" in actions
            assert "provision_ready" in actions
            assert "bind" in actions

            r = await c.post(f"/api/settings/maa/slots/{slot_id}/stop", headers=ah)
            assert r.status_code == 200
            r = await c.post(
                "/api/internal/maa/heartbeat",
                headers=wh,
                json={
                    "slot_id": slot_id,
                    "status": "offline",
                    "clear_desired_action": True,
                    "audit_action": "stop_ok",
                    "audit_result": "success",
                },
            )
            assert r.json()["status"] == "offline"

            r = await c.post(f"/api/settings/maa/slots/{slot_id}/destroy", headers=ah)
            assert r.status_code == 200
            r = await c.post(
                "/api/internal/maa/heartbeat",
                headers=wh,
                json={
                    "slot_id": slot_id,
                    "status": "destroyed",
                    "clear_desired_action": True,
                    "audit_action": "destroy_ok",
                    "audit_result": "success",
                },
            )
            assert r.json()["status"] == "destroyed"

            r = await c.get("/api/settings/maa", headers=ah)
            assert r.json()["summary"]["active_slots"] == 0

    anyio.run(_run)


def test_maa_quota_blocks_create(maa_env):
    ah = maa_env["admin_headers"]
    wh = maa_env["worker_headers"]

    async def _run() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as c:
            for _ in range(2):
                r = await c.post("/api/settings/maa/slots", headers=ah)
                assert r.status_code == 200
                sid = r.json()["id"]
                await c.post(
                    "/api/internal/maa/heartbeat",
                    headers=wh,
                    json={
                        "slot_id": sid,
                        "status": "offline",
                        "clear_desired_action": True,
                    },
                )
            r = await c.post("/api/settings/maa/slots", headers=ah)
            assert r.status_code == 409

    anyio.run(_run)


def test_worker_auth_required(maa_env):
    async def _run() -> None:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://test",
        ) as c:
            r = await c.get("/api/internal/maa/pull")
            assert r.status_code == 401

    anyio.run(_run)
