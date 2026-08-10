"""本地 MAA 业务流模拟（控制面 + Worker 回调；无 Redroid）。

覆盖：新增 → Worker 供给/上线 → 绑定 → 用户日常/截图 → 下线/销毁。
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import httpx
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.core.timeutil import now_naive
from app.models.maa import MaaSlot
from app.models.member import Member
from app.models.user import User, UserRole
from app.services import maa_slots as svc
from app.services.platform_features import (
    invalidate_feature_cache,
    load_feature_flags,
    save_feature_flags,
)

BASE = "http://127.0.0.1:8000"
TOKEN = get_settings().MAA_WORKER_TOKEN
assert TOKEN, "MAA_WORKER_TOKEN empty — 请在 .env 配置后重启后端"


def _admin(db: SessionLocal) -> User:  # type: ignore[valid-type]
    admin = db.query(User).filter(User.role == UserRole.admin).first()
    if not admin:
        raise SystemExit("no admin user")
    return admin


def _ensure_member(db) -> Member:
    m = db.query(Member).order_by(Member.id.asc()).first()
    if m:
        return m
    user = (
        db.query(User)
        .filter(User.role == UserRole.user)
        .order_by(User.id.asc())
        .first()
    )
    if not user:
        raise SystemExit("need at least one member/user")
    m = Member(nickname="maa-smoke", user_id=user.id)
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def _enable_maa_feature(db) -> None:
    flags = load_feature_flags(db)
    flags["skland"] = True
    flags["skland.arknights"] = True
    flags["skland.arknights.maa"] = True
    save_feature_flags(db, flags)
    invalidate_feature_cache()


def _clean_active_slots(db) -> None:
    for s in db.query(MaaSlot).filter(MaaSlot.status != "destroyed").all():
        s.status = "destroyed"
        s.desired_action = None
        s.bound_member_id = None
        s.destroyed_at = now_naive()
        print("cleaned leftover slot", s.id)
    db.commit()


def _write_shot(slot_id: int) -> str:
    settings = get_settings()
    data = Path(settings.DATA_DIR)
    if not data.is_absolute():
        data = (ROOT / data).resolve()
    rel = f"maa/{slot_id}/latest.jpg"
    path = data / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    Image.new("RGB", (720, 1280), (16, 80, 120)).save(buf, format="JPEG", quality=80)
    path.write_bytes(buf.getvalue())
    return rel.replace("\\", "/")


def main() -> None:
    wh = {"X-Maa-Worker-Token": TOKEN}
    db = SessionLocal()
    try:
        admin = _admin(db)
        member = _ensure_member(db)
        _enable_maa_feature(db)
        _clean_active_slots(db)
        slot = svc.create_slot(db, admin)
        sid = slot.id
        print("1) created slot", sid, slot.status, slot.desired_action)
        member_id = member.id
        # 找绑定用户的登录名
        user = db.query(User).filter(User.id == member.user_id).first()
        if not user:
            raise SystemExit("member has no user")
        user_token = create_access_token(user.username)
        admin_token = create_access_token(admin.username)
    finally:
        db.close()

    uh = {"Authorization": f"Bearer {user_token}"}
    ah = {"Authorization": f"Bearer {admin_token}"}

    with httpx.Client(base_url=BASE, timeout=30) as c:
        # admin list
        r = c.get("/api/settings/maa", headers=ah)
        r.raise_for_status()
        summary = r.json()["summary"]
        print("2) admin list", json.dumps(summary, ensure_ascii=False))

        # worker pull
        r = c.get("/api/internal/maa/pull", headers=wh)
        r.raise_for_status()
        assert any(s["id"] == sid for s in r.json()["slots"])
        print("3) worker pull ok")

# provision (auto-ready: create Android and go online)
        r = c.post(
            "/api/internal/maa/heartbeat",
            headers=wh,
            json={
                "slot_id": sid,
                "status": "online",
                "clear_desired_action": True,
                "container_name": f"zhange-maa-slot-{sid}",
                "volume_name": f"zhange-maa-slot-{sid}-data",
                "adb_endpoint": f"127.0.0.1:{5555 + sid}",
                "audit_action": "provision_ready",
                "audit_result": "success",
                "audit_message": "business-flow sim ready",
            },
        )
        r.raise_for_status()
        assert r.json()["status"] == "online"
        print("4) provision -> online (ready)")

        # bind (already online, skip start)
        r = c.post(
            f"/api/settings/maa/slots/{sid}/bind",
            headers=ah,
            json={"member_id": member_id},
        )
        r.raise_for_status()
        assert r.json()["bound_member_id"] == member_id
        print("5) bound member", member_id)

        # user me
        r = c.get("/api/maa/me", headers=uh)
        r.raise_for_status()
        me = r.json()
        assert me["assigned"] is True
        assert me["slot"]["status"] == "online"
        print("6) user /maa/me ok")

        # daily job
        r = c.post("/api/maa/me/daily", headers=uh)
        r.raise_for_status()
        job_id = r.json()["id"]
        assert r.json()["status"] == "queued"
        print("7) daily queued", job_id)

        r = c.post(
            "/api/internal/maa/jobs/update",
            headers=wh,
            json={"job_id": job_id, "status": "running"},
        )
        r.raise_for_status()
        rel = _write_shot(sid)
        r = c.post(
            "/api/internal/maa/heartbeat",
            headers=wh,
            json={
                "slot_id": sid,
                "screenshot_relpath": rel,
                "cpu_percent": "35.0",
                "memory_usage_mb": "900.0",
            },
        )
        r.raise_for_status()
        assert r.json()["has_screenshot"] is True
        r = c.post(
            "/api/internal/maa/jobs/update",
            headers=wh,
            json={"job_id": job_id, "status": "success"},
        )
        r.raise_for_status()
        print("9) daily success + screenshot")

        # user screenshot
        r = c.get("/api/maa/me/screenshot", headers=uh)
        r.raise_for_status()
        assert len(r.content) > 100
        print("10) user screenshot bytes", len(r.content))

        # admin screenshot + audits
        r = c.get(f"/api/settings/maa/slots/{sid}/screenshot", headers=ah)
        r.raise_for_status()
        r = c.get(f"/api/settings/maa/slots/{sid}/audits", headers=ah)
        r.raise_for_status()
        actions = {a["action"] for a in r.json()}
        assert "create" in actions and "bind" in actions
        print("11) audits", sorted(actions))

        # stop + destroy
        db = SessionLocal()
        try:
            svc.request_stop(db, _admin(db), sid)
        finally:
            db.close()
        r = c.post(
            "/api/internal/maa/heartbeat",
            headers=wh,
            json={
                "slot_id": sid,
                "status": "offline",
                "clear_desired_action": True,
                "audit_action": "stop_ok",
                "audit_result": "success",
            },
        )
        r.raise_for_status()
        print("12) offline")

        db = SessionLocal()
        try:
            svc.request_destroy(db, _admin(db), sid)
        finally:
            db.close()
        r = c.post(
            "/api/internal/maa/heartbeat",
            headers=wh,
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

        r = c.get("/api/settings/maa", headers=ah)
        r.raise_for_status()
        assert r.json()["summary"]["active_slots"] == 0
        print("13) destroyed, active_slots=0")

    print("BUSINESS_FLOW_OK")


if __name__ == "__main__":
    main()
