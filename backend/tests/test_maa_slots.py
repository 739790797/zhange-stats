"""MAA 槽位状态机单测（无 Docker）。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.services import maa_slots as svc


def _slot_query(slot):
    q = MagicMock()
    q.options.return_value.filter.return_value.first.return_value = slot
    q.filter.return_value.first.return_value = slot
    return q


def test_request_start_rejects_non_offline():
    db = MagicMock()
    slot = SimpleNamespace(id=1, status="online", desired_action=None)
    db.query.return_value = _slot_query(slot)
    admin = SimpleNamespace(id=9)
    with pytest.raises(HTTPException) as ei:
        svc.request_start(db, admin, 1)  # type: ignore[arg-type]
    assert ei.value.status_code == 400


def test_request_destroy_rejects_online():
    db = MagicMock()
    slot = SimpleNamespace(id=1, status="online", desired_action=None)
    db.query.return_value = _slot_query(slot)
    admin = SimpleNamespace(id=9)
    with pytest.raises(HTTPException) as ei:
        svc.request_destroy(db, admin, 1)  # type: ignore[arg-type]
    assert ei.value.status_code == 400


def test_request_start_sets_desired_action():
    db = MagicMock()
    slot = SimpleNamespace(
        id=1,
        status="offline",
        desired_action=None,
        last_error="x",
    )
    db.query.return_value = _slot_query(slot)
    admin = SimpleNamespace(id=9)
    out = svc.request_start(db, admin, 1)  # type: ignore[arg-type]
    assert out.desired_action == "start"
    assert out.last_error is None
    db.commit.assert_called()


def test_user_availability_available(monkeypatch):
    db = MagicMock()
    slots = [
        SimpleNamespace(status="online", bound_member_id=None),
        SimpleNamespace(status="online", bound_member_id=2),
    ]
    monkeypatch.setattr(svc, "list_slots", lambda *_a, **_k: slots)
    tip = svc.user_availability(db)
    assert tip["availability"] == "available"
    assert tip["free_online_slots"] == 1
    assert "就绪空闲" in tip["message"]


def test_user_availability_full(monkeypatch):
    db = MagicMock()
    slots = [
        SimpleNamespace(status="online", bound_member_id=1),
        SimpleNamespace(status="offline", bound_member_id=2),
    ]
    monkeypatch.setattr(svc, "list_slots", lambda *_a, **_k: slots)
    tip = svc.user_availability(db)
    assert tip["availability"] == "full"
