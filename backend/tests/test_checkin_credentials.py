"""平台凭证写回：没变不写、变了按读出时的密文 CAS、同成员换票串行且进锁后重读。"""

from __future__ import annotations

import json
import threading
import time
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core import crypto_secret
from app.core.crypto_secret import decrypt_secret, encrypt_secret
from app.core.database import Base
from app.models.member import Member
from app.models.taygedo import TaygedoBind
from app.services.checkin.credentials import (
    StoredCreds,
    refresh_creds_locked,
    store_creds_if_changed,
)
from app.services.taygedo.client import TaygedoCredentials


@pytest.fixture(autouse=True)
def _fixed_secret(monkeypatch):
    holder = SimpleNamespace(SECRET_KEY="unit-test-secret-key-0123456789abcdef")
    monkeypatch.setattr(crypto_secret, "get_settings", lambda: holder)


def _creds(refresh: str = "r0", *, phone: str | None = None) -> TaygedoCredentials:
    return TaygedoCredentials(
        uid="u1",
        device_id="dev",
        access_token=f"a-{refresh}",
        refresh_token=refresh,
        phone=phone,
    )


def _enc(creds: Any) -> str:
    return encrypt_secret(json.dumps(creds.to_dict(), ensure_ascii=False))


def _load(bind: TaygedoBind) -> TaygedoCredentials:
    return TaygedoCredentials.from_dict(json.loads(decrypt_secret(bind.credentials_enc)))


@pytest.fixture
def make_db(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'creds.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False)
    opened = []

    def make():
        db = factory()
        opened.append(db)
        return db

    yield make
    for db in opened:
        db.close()
    engine.dispose()


@pytest.fixture
def bind_id(make_db) -> int:
    db = make_db()
    db.add(Member(id=1, nickname="m1"))
    bind = TaygedoBind(member_id=1, credentials_enc=_enc(_creds()), phone_mask="old")
    db.add(bind)
    db.commit()
    return bind.id


def _stored_refresh(make_db, bind_id: int) -> str:
    return _load(make_db().get(TaygedoBind, bind_id)).refresh_token


def test_unchanged_creds_are_not_written(make_db, bind_id) -> None:
    db = make_db()
    bind = db.get(TaygedoBind, bind_id)
    before = (bind.credentials_enc, bind.updated_at)
    stored = StoredCreds.snapshot(bind, _load(bind))

    out = store_creds_if_changed(db, bind, stored, extra={"phone_mask": "new"})
    db.commit()

    assert out is stored
    db.expire_all()
    assert (bind.credentials_enc, bind.updated_at, bind.phone_mask) == (*before, "old")


def test_changed_creds_are_written_and_snapshot_rebased(make_db, bind_id) -> None:
    db = make_db()
    bind = db.get(TaygedoBind, bind_id)
    stored = StoredCreds.snapshot(bind, _load(bind))

    out = store_creds_if_changed(
        db,
        bind,
        stored.with_creds(_creds("r1", phone="13800001234")),
        extra={"phone_mask": "138****1234"},
    )
    db.commit()

    assert _stored_refresh(make_db, bind_id) == "r1"
    assert bind.phone_mask == "138****1234"
    assert out.loaded_enc == bind.credentials_enc
    assert store_creds_if_changed(db, bind, out) is out


def test_in_place_mutation_is_detected(make_db, bind_id) -> None:
    db = make_db()
    bind = db.get(TaygedoBind, bind_id)
    stored = StoredCreds.snapshot(bind, _load(bind))
    stored.creds.access_token = "patched-in-place"

    store_creds_if_changed(db, bind, stored)
    db.commit()

    assert _load(make_db().get(TaygedoBind, bind_id)).access_token == "patched-in-place"


def test_rebind_in_flight_is_not_overwritten(make_db, bind_id) -> None:
    db = make_db()
    bind = db.get(TaygedoBind, bind_id)
    stored = StoredCreds.snapshot(bind, _load(bind))
    db.commit()

    other = make_db()
    other.get(TaygedoBind, bind_id).credentials_enc = _enc(_creds("rebound"))
    other.commit()

    attempt = stored.with_creds(_creds("r1"))
    out = store_creds_if_changed(db, bind, attempt)
    db.commit()

    assert out is attempt
    assert _stored_refresh(make_db, bind_id) == "rebound"
    assert store_creds_if_changed(db, bind, out) is out
    db.commit()
    assert _stored_refresh(make_db, bind_id) == "rebound"


def test_refresh_is_serialized_per_member_and_rereads_rotated_token(make_db, bind_id) -> None:
    seen: list[str] = []
    active = {"now": 0, "max": 0}
    guard = threading.Lock()
    first_in = threading.Event()
    release_first = threading.Event()
    errors: list[BaseException] = []

    def rotate(creds: TaygedoCredentials) -> TaygedoCredentials:
        with guard:
            first = not seen
            seen.append(creds.refresh_token)
            active["now"] += 1
            active["max"] = max(active["max"], active["now"])
        if first:
            first_in.set()
            release_first.wait(timeout=5)
        with guard:
            active["now"] -= 1
        return _creds(f"r{int(creds.refresh_token[1:]) + 1}")

    def worker() -> None:
        try:
            db = make_db()
            bind = db.get(TaygedoBind, bind_id)
            refresh_creds_locked(db, bind, platform="taygedo", load=_load, refresh=rotate)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    first = threading.Thread(target=worker)
    first.start()
    assert first_in.wait(timeout=5)
    second = threading.Thread(target=worker)
    second.start()
    time.sleep(0.05)
    release_first.set()
    first.join(timeout=5)
    second.join(timeout=5)

    assert not errors
    assert seen == ["r0", "r1"]
    assert active["max"] == 1
    assert _stored_refresh(make_db, bind_id) == "r2"


def _platform(name: str) -> SimpleNamespace:
    """签到时接口会原地换 token 的平台：bind 模型、初始/重绑凭证、要替换的上游入口。"""
    if name == "mihoyo":
        from app.models.mihoyo import MihoyoBind
        from app.services.mihoyo.checkin import mihoyo_adapter
        from app.services.mihoyo.client import MihoyoCredentials

        return SimpleNamespace(
            adapter=mihoyo_adapter,
            bind_model=MihoyoBind,
            creds=MihoyoCredentials(cookie="stuid=1; stoken=s; cookie_token=c0", nickname="n"),
            rebound=MihoyoCredentials(cookie="stuid=9; stoken=s9; cookie_token=c9"),
            patches={"app.services.mihoyo.client.ensure_session": lambda c: c},
            run_target="app.services.mihoyo.checkin.run_all_checkins",
            token_field="cookie",
        )
    if name == "exilium":
        from app.models.exilium import ExiliumBind
        from app.services.exilium.checkin import exilium_adapter
        from app.services.exilium.client import ExiliumCredentials

        return SimpleNamespace(
            adapter=exilium_adapter,
            bind_model=ExiliumBind,
            creds=ExiliumCredentials(token="t0", user_id="u1"),
            rebound=ExiliumCredentials(token="t9", user_id="u9"),
            patches={"app.services.exilium.checkin.ensure_session": lambda c: c},
            run_target="app.services.exilium.checkin.checkin",
            token_field="token",
        )
    from app.models.kujiequ import KujiequBind
    from app.services.kujiequ.checkin import kujiequ_adapter
    from app.services.kujiequ.client import KujiequCredentials

    return SimpleNamespace(
        adapter=kujiequ_adapter,
        bind_model=KujiequBind,
        creds=KujiequCredentials(token="t0", user_id="u1", distinct_id="d", dev_code="D"),
        rebound=KujiequCredentials(token="t9", user_id="u9", distinct_id="d9", dev_code="D9"),
        patches={},
        run_target="app.services.kujiequ.checkin.run_all_checkins",
        token_field="token",
    )


@pytest.mark.parametrize("rebind", [False, True], ids=["refresh", "rebind"])
@pytest.mark.parametrize("platform", ["mihoyo", "exilium", "kujiequ"])
def test_checkin_writes_back_refreshed_token_unless_rebound(
    monkeypatch, make_db, platform, rebind
) -> None:
    from app.services.checkin.common import CheckinResult
    from app.services.checkin.orchestrator import run_checkin_for_bind

    spec = _platform(platform)
    db = make_db()
    db.add(Member(id=2, nickname="m2"))
    bind = spec.bind_model(member_id=2, credentials_enc=_enc(spec.creds), auto_checkin=True)
    db.add(bind)
    db.commit()
    bind_id = bind.id
    rebound_enc = _enc(spec.rebound)
    for target, fn in spec.patches.items():
        monkeypatch.setattr(target, fn)

    def run(creds, **_kwargs):
        setattr(creds, spec.token_field, f"{getattr(creds, spec.token_field)}; refreshed")
        if rebind:
            other = make_db()
            other.get(spec.bind_model, bind_id).credentials_enc = rebound_enc
            other.commit()
        ok = CheckinResult(
            game_code="x",
            game_name="x",
            role_uid="u1",
            role_name="-",
            channel_name="-",
            status="ok",
            message="ok",
        )
        return creds, [ok]

    monkeypatch.setattr(spec.run_target, run)

    out = run_checkin_for_bind(spec.adapter, db, bind, force=True)

    assert out["ok"] is True
    stored = make_db().get(spec.bind_model, bind_id).credentials_enc
    if rebind:
        assert stored == rebound_enc
    else:
        token = json.loads(decrypt_secret(stored))[spec.token_field]
        assert token.endswith("; refreshed")
