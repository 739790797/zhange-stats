"""本地无 Docker 冒烟：直接写库建槽 + 调 Worker 内部 API 走完生命周期。"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import httpx
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.maa import MaaSlot
from app.models.user import User
from app.services import maa_slots as svc

BASE = "http://127.0.0.1:8000"
TOKEN = get_settings().MAA_WORKER_TOKEN
assert TOKEN, "MAA_WORKER_TOKEN empty"


def _admin(db):
    from app.models.user import UserRole

    admin = db.query(User).filter(User.role == UserRole.admin).first()
    if not admin:
        raise SystemExit("no admin user")
    return admin


def main() -> None:
    headers = {"X-Maa-Worker-Token": TOKEN}
    db = SessionLocal()
    try:
        admin = _admin(db)
        # 清理上次失败留下的 active 槽，避免干扰
        leftovers = (
            db.query(MaaSlot).filter(MaaSlot.status != "destroyed").all()
        )
        for s in leftovers:
            s.status = "destroying"
            s.desired_action = "destroy"
            s.bound_member_id = None
            db.commit()
            # 直接标 destroyed（冒烟环境无 Docker）
            s.status = "destroyed"
            s.desired_action = None
            from app.core.timeutil import now_naive

            s.destroyed_at = now_naive()
            db.commit()
            print("cleaned leftover slot", s.id)
        slot = svc.create_slot(db, admin)
        sid = slot.id
        print("created", sid, slot.status, slot.desired_action)
    finally:
        db.close()

    with httpx.Client(base_url=BASE, timeout=30) as c:
        r = c.get("/api/internal/maa/pull", headers=headers)
        r.raise_for_status()
        assert any(s["id"] == sid for s in r.json()["slots"]), r.text
        print("pull ok")

        r = c.post(
            "/api/internal/maa/heartbeat",
            headers=headers,
            json={
                "slot_id": sid,
                "status": "offline",
                "clear_desired_action": True,
                "container_name": f"zhange-maa-slot-{sid}",
                "volume_name": f"zhange-maa-slot-{sid}-data",
                "adb_endpoint": f"127.0.0.1:{5555 + sid}",
                "audit_action": "provision_ok",
                "audit_result": "success",
                "audit_message": "live smoke provision",
            },
        )
        r.raise_for_status()
        assert r.json()["status"] == "offline"
        print("provision -> offline")

        db = SessionLocal()
        try:
            svc.request_start(db, _admin(db), sid)
        finally:
            db.close()

        r = c.post(
            "/api/internal/maa/heartbeat",
            headers=headers,
            json={
                "slot_id": sid,
                "status": "online",
                "clear_desired_action": True,
                "cpu_percent": "1.0",
                "memory_usage_mb": "100.0",
                "audit_action": "start_ok",
                "audit_result": "success",
            },
        )
        r.raise_for_status()
        assert r.json()["status"] == "online"
        print("online")

        settings = get_settings()
        data = Path(settings.DATA_DIR)
        if not data.is_absolute():
            data = (ROOT / data).resolve()
        rel = f"maa/{sid}/latest.jpg"
        path = data / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        buf = io.BytesIO()
        Image.new("RGB", (640, 360), (20, 20, 40)).save(buf, format="JPEG")
        path.write_bytes(buf.getvalue())

        r = c.post(
            "/api/internal/maa/heartbeat",
            headers=headers,
            json={"slot_id": sid, "screenshot_relpath": rel},
        )
        r.raise_for_status()
        assert r.json()["has_screenshot"] is True
        print("screenshot ok", path)

        db = SessionLocal()
        try:
            svc.request_stop(db, _admin(db), sid)
        finally:
            db.close()
        r = c.post(
            "/api/internal/maa/heartbeat",
            headers=headers,
            json={
                "slot_id": sid,
                "status": "offline",
                "clear_desired_action": True,
                "audit_action": "stop_ok",
                "audit_result": "success",
            },
        )
        r.raise_for_status()

        db = SessionLocal()
        try:
            svc.request_destroy(db, _admin(db), sid)
        finally:
            db.close()
        r = c.post(
            "/api/internal/maa/heartbeat",
            headers=headers,
            json={
                "slot_id": sid,
                "status": "destroyed",
                "clear_desired_action": True,
                "audit_action": "destroy_ok",
                "audit_result": "success",
            },
        )
        r.raise_for_status()
        assert r.json()["status"] == "destroyed"
        print("destroyed ok")

    print("LIVE_SMOKE_OK")


if __name__ == "__main__":
    main()
