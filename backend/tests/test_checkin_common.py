"""checkin_common 纯函数单测（无 DB）。"""

from app.services.checkin_common import (
    CheckinResult,
    apply_bind_last_checkin,
    is_placeholder_awards,
    is_success_status,
    prefer_richer_awards,
    status_label,
    summarize_results,
)


def test_is_success_status() -> None:
    assert is_success_status("ok")
    assert is_success_status("already")
    assert not is_success_status("pending")
    assert not is_success_status("error")
    assert not is_success_status(None)


def test_status_label() -> None:
    assert status_label("ok") == "已签"
    assert status_label("already") == "已签"
    assert status_label("pending") == "未签"


def test_placeholder_awards() -> None:
    assert is_placeholder_awards(None)
    assert is_placeholder_awards("奖励×2")
    assert not is_placeholder_awards("源石×2")


def test_prefer_richer_awards() -> None:
    assert prefer_richer_awards("奖励×1", "源石×2") == "源石×2"
    assert prefer_richer_awards("源石×2", "奖励×1") == "源石×2"


def test_summarize_results() -> None:
    ok, summary = summarize_results([], empty_message="空")
    assert ok is False
    assert summary == "空"
    results = [
        CheckinResult("g", "游戏", "1", "角色", "官服", "ok", "成功"),
    ]
    ok, summary = summarize_results(results, empty_message="空")
    assert ok is True
    assert "已" in summary or "成功" in summary


def test_apply_bind_last_checkin() -> None:
    class Bind:
        last_checkin_at = None
        last_checkin_date = None
        last_checkin_ok = None
        last_checkin_summary = None
        updated_at = None

    bind = Bind()
    apply_bind_last_checkin(
        bind, now="now", checkin_date="2026-08-05", ok=True, summary="ok"
    )
    assert bind.last_checkin_ok is True
    assert bind.last_checkin_summary == "ok"
    assert bind.updated_at == "now"
