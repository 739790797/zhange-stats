"""森空岛：失效 cred 缓存遇鉴权错误时清缓存并换票重试。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services.skland_checkin import (
    _looks_like_skland_auth_error,
    query_today_for_bind,
)
from app.services.skland_client import SklandApiError, SklandSession


def test_looks_like_skland_auth_error():
    assert _looks_like_skland_auth_error("用户未登录")
    assert _looks_like_skland_auth_error("凭证可能已失效，请重新绑定森空岛（用户未登录）")
    assert not _looks_like_skland_auth_error("网络超时")
    assert not _looks_like_skland_auth_error("")


def test_query_today_retries_once_after_auth_error(monkeypatch):
    bind = SimpleNamespace(member_id=9, id=1, token_enc="enc")
    session = SklandSession(cred="c2", sign_token="s2")
    calls = {"orch": 0}

    def orch(_adapter, _db, _bind, *, force=False):
        calls["orch"] += 1
        if calls["orch"] == 1:
            raise SklandApiError("用户未登录", code=10001)
        return {"results": [], "summary": "ok", "force": force}

    inv = MagicMock()
    fresh = MagicMock(return_value=session)

    monkeypatch.setattr(
        "app.services.skland_checkin._orch_query_today", orch
    )
    monkeypatch.setattr(
        "app.services.skland_session_cache.invalidate_skland_session", inv
    )
    monkeypatch.setattr(
        "app.services.skland_checkin._session_for_bind", fresh
    )

    out = query_today_for_bind(MagicMock(), bind, force=False)
    assert out["summary"] == "ok"
    assert calls["orch"] == 2
    inv.assert_called_once_with(9)
    fresh.assert_called_once_with(bind, bypass_cache=True)


def test_query_today_does_not_retry_non_auth(monkeypatch):
    bind = SimpleNamespace(member_id=9, id=1, token_enc="enc")

    def orch(*_a, **_k):
        raise SklandApiError("网络超时")

    monkeypatch.setattr(
        "app.services.skland_checkin._orch_query_today", orch
    )
    with pytest.raises(SklandApiError, match="网络超时"):
        query_today_for_bind(MagicMock(), bind, force=True)
