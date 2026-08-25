"""checkin_common 纯函数单测（无 DB）。"""

from datetime import date

from app.services.checkin.common import (
    CheckinResult,
    apply_bind_last_checkin,
    is_placeholder_awards,
    is_success_status,
    prefer_richer_awards,
    status_label,
    summarize_results,
    upsert_and_reload_day_results,
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
    # 占位视为无效：同步拿不到更好结果时清空，避免长期展示「奖励×N」
    assert prefer_richer_awards("奖励 × 10", None) is None
    assert prefer_richer_awards("奖励×2", "") is None
    # 完整奖励不被空 incoming 抹掉
    assert prefer_richer_awards("源石×2", None) == "源石×2"


def test_prefer_richer_drops_polluted_task_exp_awards() -> None:
    from app.services.checkin.common import (
        is_polluted_task_exp_awards,
        prefer_richer_award_items,
    )

    polluted = "点赞帖子+2、点赞帖子+2、浏览帖子+5、签到+5"
    assert is_polluted_task_exp_awards(polluted)
    # 污染 + 弱经验签到文案都视为无效
    assert prefer_richer_awards(polluted, "签到奖励+10") is None
    assert prefer_richer_awards(polluted, None) is None
    assert prefer_richer_awards(polluted, "塔塔币+40") == "塔塔币+40"
    assert prefer_richer_awards("签到奖励+10", "塔塔币+40") == "塔塔币+40"
    polluted_items = [
        {"name": "点赞帖子", "count": 2},
        {"name": "浏览帖子", "count": 5},
        {"name": "签到", "count": 5},
    ]
    clean_items = [{"name": "塔塔币", "count": 40, "resource_type": "gold"}]
    assert (
        prefer_richer_award_items(
            polluted, polluted_items, "塔塔币+40", clean_items
        )
        == clean_items
    )
    assert prefer_richer_award_items(polluted, polluted_items, None, None) is None


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


def test_upsert_and_reload_preserves_extra_text() -> None:
    """logs 无 extra_text 列；读回后须从现场 results 回填（追放每日任务）。"""

    class _Log:
        member_id = object()
        checkin_date = object()
        game_code = object()
        role_uid = object()
        awards_json = object()
        source = object()

        def __init__(self, **kw):
            for k, v in kw.items():
                setattr(self, k, v)

    class _Query:
        def __init__(self, rows):
            self._rows = rows

        def filter(self, *a, **k):
            return self

        def one_or_none(self):
            return self._rows[0] if self._rows else None

        def all(self):
            return list(self._rows)

    class _Db:
        def __init__(self):
            self.rows: list = []

        def query(self, model):
            return _Query(self.rows)

        def add(self, row):
            self.rows.append(row)

        def flush(self):
            return None

    live = CheckinResult(
        game_code="exilium",
        game_name="追放社区",
        role_uid="u1",
        role_name="指挥官",
        channel_name="社区",
        status="already",
        message="今日已签到",
        awards_text="积分+40",
        extra_text="每日任务：浏览 3/3 · 点赞 3/3 · 分享 1/1（积分+30）",
        awards=[{"name": "积分", "count": 40, "resource_type": "score"}],
    )
    db = _Db()
    merged = upsert_and_reload_day_results(
        db,
        _Log,
        member_id=1,
        bind_id=1,
        checkin_date=date(2026, 8, 7),
        results=[live],
        now=date(2026, 8, 7),
    )
    assert len(merged) == 1
    assert merged[0].extra_text == live.extra_text
    assert merged[0].awards_text == "积分+40"
    # message 落库时会并入 extra_text，但 API 展示字段仍独立
    assert "每日任务" in (db.rows[0].message or "")
