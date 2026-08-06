"""B服 query_role_today：records 空不得误判未签。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import app.services.skland_client  # noqa: F401 — 解开 attendance↔client 环依赖
from app.services.checkin_common import STATUS_UNKNOWN
from app.services.skland_attendance import query_role_today
from app.services.skland_client import GAME_ARKNIGHTS


def test_bilibili_empty_records_is_unknown_not_pending() -> None:
    role = SimpleNamespace(
        game_code=GAME_ARKNIGHTS,
        game_name="明日方舟",
        uid="52430798",
        role_name="白衣#0719",
        channel_name="B服",
        channel_master_id="2",
        role_id=None,
        server_id=None,
    )
    empty = {"code": 0, "data": {"records": [], "calendar": [{"done": False}]}}

    with patch(
        "app.services.skland_attendance._attendance_get",
        return_value=empty,
    ):
        result = query_role_today(SimpleNamespace(), role)  # type: ignore[arg-type]

    assert result.status == STATUS_UNKNOWN
    assert "领取记录" in (result.message or "")
