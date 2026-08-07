"""ephemeral_kv + skland session/qr 短时存储。"""

from __future__ import annotations

import json
import time

import pytest

from app.core.ephemeral_kv import (
    ephemeral_delete,
    ephemeral_get,
    ephemeral_set,
    reset_ephemeral_kv_for_tests,
)
from app.services.skland_client import SklandSession
from app.services.skland_session_cache import (
    get_cached_skland_session,
    invalidate_skland_session,
    put_cached_skland_session,
)


@pytest.fixture(autouse=True)
def _clean_kv(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "")
    reset_ephemeral_kv_for_tests()
    yield
    reset_ephemeral_kv_for_tests()


def test_ephemeral_set_get_delete():
    ephemeral_set("k", "v", ttl_sec=60)
    assert ephemeral_get("k") == "v"
    ephemeral_delete("k")
    assert ephemeral_get("k") is None


def test_ephemeral_ttl_expires(monkeypatch):
    import app.core.ephemeral_kv as kv

    clock = {"t": 1_000.0}
    monkeypatch.setattr(kv.time, "time", lambda: clock["t"])
    ephemeral_set("k2", "v2", ttl_sec=5)
    assert ephemeral_get("k2") == "v2"
    clock["t"] = 1_006.0
    assert ephemeral_get("k2") is None


def test_skland_session_cache_roundtrip():
    session = SklandSession(cred="c1", sign_token="s1")
    put_cached_skland_session(7, "hg-token-aaa", session)
    hit = get_cached_skland_session(7, "hg-token-aaa")
    assert hit is not None
    assert hit.cred == "c1"
    assert hit.sign_token == "s1"


def test_skland_session_cache_token_mismatch_invalidates():
    put_cached_skland_session(
        7, "hg-token-aaa", SklandSession(cred="c1", sign_token="s1")
    )
    assert get_cached_skland_session(7, "hg-token-bbb") is None
    assert get_cached_skland_session(7, "hg-token-aaa") is None


def test_skland_session_invalidate():
    put_cached_skland_session(
        3, "tok", SklandSession(cred="c", sign_token="s")
    )
    invalidate_skland_session(3)
    assert get_cached_skland_session(3, "tok") is None


def test_qr_pending_json_roundtrip():
    from app.services import skland_qr

    payload = {
        "user_id": 1,
        "member_id": 2,
        "device_id": "abc",
        "scan_url": "https://example/scan",
        "created_at": time.time(),
        "completed": False,
    }
    skland_qr._save_pending("scan-1", payload, remaining_ttl=60)
    loaded = skland_qr._load_pending("scan-1")
    assert loaded is not None
    assert loaded["device_id"] == "abc"
    assert json.loads(ephemeral_get("skland:qr:scan-1") or "{}")["user_id"] == 1
