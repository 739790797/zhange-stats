"""任务账清空边界：清空进度 / 转生之后，回放下限落库、只增不减，跨设备与登出仍然生效。"""

from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.models.tarkov import TarkovUserTaskCleared, TarkovUserTaskReset
from app.models.user import User, UserRole
from app.services.tarkov import task_dones as dones


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _user(db: Session, username: str = "a") -> User:
    row = User(
        username=username,
        display_name=username,
        password_hash="x",
        role=UserRole.user,
    )
    db.add(row)
    db.flush()
    return row


def _seed(db: Session, user: User, mode: str = "pvp") -> None:
    dones.write_progress(
        db,
        user,
        ["old-done"],
        ["old-start"],
        replace=True,
        game_mode=mode,
        failed_ids=["old-fail"],
        objective_dones=[{"task_id": "old-done", "objective_id": "step"}],
    )


T_CLEAR = datetime(2026, 10, 13, 15, 0, 0)


def test_boundary_defaults_to_nothing() -> None:
    db = _session()
    user = _user(db)
    assert dones.task_boundary(db, user.id, game_mode="pvp") == {
        "reset_at": None,
        "pending_clear_at": None,
        "profile_id": "",
        "epoch": 0,
    }
    assert dones.list_cleared(db, user.id, game_mode="pvp") == []


def test_clear_progress_wipes_mode_and_records_pending_clear() -> None:
    db = _session()
    user = _user(db)
    _seed(db, user, "pvp")
    _seed(db, user, "pve")
    out = dones.clear_progress(db, user, game_mode="pvp", now=T_CLEAR)
    assert out["pending_clear_at"] == "2026-10-13 15:00:00"
    assert out["reset_at"] is None
    assert out["epoch"] == 1
    done, started, failed, objectives = dones.account_progress(db, user.id, game_mode="pvp")
    assert (done, started, failed, objectives) == ([], [], [], [])
    # PVE untouched
    done, started, failed, objectives = dones.account_progress(db, user.id, game_mode="pve")
    assert done == ["old-done"]
    assert dones.task_boundary(db, user.id, game_mode="pve")["epoch"] == 0


def test_clear_survives_as_server_state_not_client_state() -> None:
    """登出 / 换浏览器之后，边界仍可从账号读回（以前只存在 localStorage）。"""
    db = _session()
    user = _user(db)
    _seed(db, user)
    dones.clear_progress(db, user, game_mode="pvp", now=T_CLEAR)
    db.commit()
    fresh = sessionmaker(bind=db.get_bind())()
    assert dones.task_boundary(fresh, user.id, game_mode="pvp")["pending_clear_at"] == (
        "2026-10-13 15:00:00"
    )


def test_reset_clear_floor_never_earlier_than_pending_clear() -> None:
    """同一角色清空：哪怕客户端算出更早的时刻，下限也不早于玩家点清空的那一刻。"""
    db = _session()
    user = _user(db)
    dones.clear_progress(db, user, game_mode="pvp", now=T_CLEAR)
    out = dones.apply_reset(
        db,
        user,
        reset_at="2026-06-01 10:00:00",
        profile_id="aa11",
        reason="clear",
        epoch=1,
        task_ids=["new-done"],
        started_ids=[],
        failed_ids=[],
        objective_dones=[],
        game_mode="pvp",
    )
    assert out["reset_at"] == "2026-10-13 15:00:00"
    assert out["pending_clear_at"] is None
    assert out["profile_id"] == "aa11"
    assert out["epoch"] == 2
    assert dones.list_task_ids(db, user.id, game_mode="pvp") == ["new-done"]


def test_reset_prestige_may_precede_the_clear() -> None:
    """识别出转生：下限取转生点；转生之后、清空之前打的任务保留。"""
    db = _session()
    user = _user(db)
    dones.clear_progress(db, user, game_mode="pvp", now=T_CLEAR)
    out = dones.apply_reset(
        db,
        user,
        reset_at="2026-10-13 10:00:00",
        profile_id="aa11",
        reason="prestige",
        epoch=1,
        task_ids=["after-prestige"],
        started_ids=[],
        failed_ids=[],
        objective_dones=[],
        game_mode="pvp",
    )
    assert out["reset_at"] == "2026-10-13 10:00:00"
    assert dones.list_task_ids(db, user.id, game_mode="pvp") == ["after-prestige"]


def test_reset_floor_is_monotonic() -> None:
    db = _session()
    user = _user(db)
    dones.apply_reset(
        db,
        user,
        reset_at="2026-10-13 15:00:00",
        profile_id="aa11",
        reason="prestige",
        epoch=0,
        task_ids=[],
        started_ids=[],
        failed_ids=[],
        objective_dones=[],
        game_mode="pvp",
    )
    with pytest.raises(dones.TarkovTaskDonesError) as exc:
        dones.apply_reset(
            db,
            user,
            reset_at="2026-06-01 10:00:00",
            profile_id="aa11",
            reason="profile",
            epoch=1,
            task_ids=["old"],
            started_ids=[],
            failed_ids=[],
            objective_dones=[],
            game_mode="pvp",
        )
    assert exc.value.status_code == 409
    assert dones.task_boundary(db, user.id, game_mode="pvp")["reset_at"] == (
        "2026-10-13 15:00:00"
    )


def test_stale_epoch_is_rejected_for_bulk_writes() -> None:
    """别的标签页 / 设备在清空之前算好的整账，清空之后不得再并回来。"""
    db = _session()
    user = _user(db)
    _seed(db, user)
    before = dones.task_boundary(db, user.id, game_mode="pvp")["epoch"]
    dones.clear_progress(db, user, game_mode="pvp", now=T_CLEAR)
    with pytest.raises(dones.TarkovTaskDonesError) as exc:
        dones.check_epoch(db, user.id, before, game_mode="pvp")
    assert exc.value.status_code == 409
    dones.check_epoch(db, user.id, 1, game_mode="pvp")
    dones.check_epoch(db, user.id, None, game_mode="pvp")


def test_bulk_write_without_epoch_is_refused_once_the_account_has_a_boundary() -> None:
    """新浏览器 / 升级前缓存的旧页面不带 epoch：账号清空过就不让它把手里的旧账并回来。"""
    db = _session()
    user = _user(db)
    # 从没清空过：不带 epoch 照旧放行（老客户端不受影响）
    dones.check_epoch(db, user.id, None, game_mode="pvp", required=True)
    dones.clear_progress(db, user, game_mode="pvp", now=T_CLEAR)
    with pytest.raises(dones.TarkovTaskDonesError) as exc:
        dones.check_epoch(db, user.id, None, game_mode="pvp", required=True)
    assert exc.value.status_code == 409
    # 另一个模式不受影响
    dones.check_epoch(db, user.id, None, game_mode="pve", required=True)
    dones.check_epoch(db, user.id, 1, game_mode="pvp", required=True)


def test_reset_rejects_stale_epoch_and_bad_input() -> None:
    db = _session()
    user = _user(db)
    dones.clear_progress(db, user, game_mode="pvp", now=T_CLEAR)
    kwargs = dict(
        profile_id="aa11",
        task_ids=[],
        started_ids=[],
        failed_ids=[],
        objective_dones=[],
        game_mode="pvp",
    )
    with pytest.raises(dones.TarkovTaskDonesError) as stale:
        dones.apply_reset(db, user, reset_at="2026-10-13 16:00:00", reason="clear", epoch=0, **kwargs)
    assert stale.value.status_code == 409
    with pytest.raises(dones.TarkovTaskDonesError):
        dones.apply_reset(db, user, reset_at="garbage", reason="clear", epoch=1, **kwargs)
    with pytest.raises(dones.TarkovTaskDonesError):
        dones.apply_reset(db, user, reset_at="2026-10-13 16:00:00", reason="nope", epoch=1, **kwargs)


def test_parse_clock_accepts_log_and_iso_shapes() -> None:
    assert dones.parse_clock("2026-10-13 15:00:00.123") == datetime(2026, 10, 13, 15, 0, 0)
    assert dones.parse_clock("2026-10-13T15:00:00") == datetime(2026, 10, 13, 15, 0, 0)
    # 带偏移的 UTC 转北京墙钟
    assert dones.parse_clock("2026-10-13T07:00:00Z") == datetime(2026, 10, 13, 15, 0, 0)


def test_manual_uncheck_is_remembered_on_the_account() -> None:
    db = _session()
    user = _user(db)
    dones.add_done(db, user, "t1", game_mode="pvp")
    dones.remove_done(db, user, "t1", game_mode="pvp", now=T_CLEAR)
    assert dones.list_cleared(db, user.id, game_mode="pvp") == [
        {"task_id": "t1", "cleared_at": "2026-10-13 15:00:00"}
    ]
    # 标回完成就释放
    dones.add_done(db, user, "t1", game_mode="pvp")
    assert dones.list_cleared(db, user.id, game_mode="pvp") == []


def test_replace_records_removed_dones_and_releases_readded() -> None:
    db = _session()
    user = _user(db)
    dones.write_progress(db, user, ["a", "b"], [], replace=True, game_mode="pvp")
    dones.write_progress(
        db, user, ["a"], [], replace=True, game_mode="pvp", now=T_CLEAR
    )
    assert [row["task_id"] for row in dones.list_cleared(db, user.id, game_mode="pvp")] == ["b"]
    dones.write_progress(db, user, ["a", "b"], [], replace=False, game_mode="pvp")
    assert dones.list_cleared(db, user.id, game_mode="pvp") == []


def test_reset_leaves_no_stale_cleared_marks() -> None:
    db = _session()
    user = _user(db)
    _seed(db, user)
    dones.remove_done(db, user, "old-done", game_mode="pvp")
    dones.clear_progress(db, user, game_mode="pvp", now=T_CLEAR)
    dones.write_progress(db, user, ["x"], [], replace=False, game_mode="pvp")
    dones.apply_reset(
        db,
        user,
        reset_at="2026-10-13 15:00:00",
        profile_id="aa11",
        reason="clear",
        epoch=1,
        task_ids=["new"],
        started_ids=[],
        failed_ids=[],
        objective_dones=[],
        game_mode="pvp",
    )
    assert db.query(TarkovUserTaskCleared).count() == 0
    assert dones.list_task_ids(db, user.id, game_mode="pvp") == ["new"]


def test_record_profile_does_not_move_the_boundary() -> None:
    db = _session()
    user = _user(db)
    out = dones.record_profile(db, user, "aa11", game_mode="pvp")
    assert out == {"reset_at": None, "pending_clear_at": None, "profile_id": "aa11", "epoch": 0}
    dones.clear_progress(db, user, game_mode="pvp", now=T_CLEAR)
    out = dones.record_profile(db, user, "bb22", game_mode="pvp")
    assert out["epoch"] == 1
    assert out["pending_clear_at"] == "2026-10-13 15:00:00"
    assert out["profile_id"] == "bb22"
    # epoch-0 accounts stay epoch 0, so bulk writes without expect_epoch keep working
    other = _user(db, "b")
    dones.record_profile(db, other, "cc33", game_mode="pvp")
    dones.check_epoch(db, other.id, None, game_mode="pvp", required=True)
    with pytest.raises(dones.TarkovTaskDonesError):
        dones.record_profile(db, user, "  ", game_mode="pvp")


def test_users_do_not_share_boundaries() -> None:
    db = _session()
    a = _user(db, "a")
    b = _user(db, "b")
    dones.clear_progress(db, a, game_mode="pvp", now=T_CLEAR)
    assert dones.task_boundary(db, b.id, game_mode="pvp")["pending_clear_at"] is None


def test_prestige_reset_keeps_manual_uncheck_newer_than_the_floor() -> None:
    """转生下限早于手动取消：取消标记要留着，否则从下限重放会把玩家亲手取消的任务带回来。"""
    db = _session()
    user = _user(db)
    dones.add_done(db, user, "x", game_mode="pvp")
    dones.remove_done(db, user, "x", game_mode="pvp", now=datetime(2026, 10, 5, 12, 0, 0))
    dones.remove_done(db, user, "y", game_mode="pvp")  # 没完成过，不记标记
    dones.write_progress(db, user, ["old"], [], replace=False, game_mode="pvp")
    dones.remove_done(db, user, "old", game_mode="pvp", now=datetime(2026, 9, 1, 0, 0, 0))
    dones.apply_reset(
        db,
        user,
        reset_at="2026-10-01 00:00:00",
        profile_id="aa11",
        reason="prestige",
        epoch=0,
        task_ids=["after"],
        started_ids=[],
        failed_ids=[],
        objective_dones=[],
        game_mode="pvp",
        now=datetime(2026, 10, 6, 0, 0, 0),
    )
    # 10-05 的取消晚于 10-01 的下限：保留；09-01 的已被下限覆盖：删掉
    assert dones.list_cleared(db, user.id, game_mode="pvp") == [
        {"task_id": "x", "cleared_at": "2026-10-05 12:00:00"}
    ]


def test_reset_does_not_stamp_marks_for_replayed_removals() -> None:
    """整表替换拿掉的旧完成是回放结果，不是手动取消：不能记成「现在」挡住别的设备的真实完成。"""
    db = _session()
    user = _user(db)
    dones.write_progress(db, user, ["a", "b"], [], replace=True, game_mode="pvp")
    dones.apply_reset(
        db,
        user,
        reset_at="2026-10-01 00:00:00",
        profile_id="aa11",
        reason="prestige",
        epoch=0,
        task_ids=["a"],
        started_ids=[],
        failed_ids=[],
        objective_dones=[],
        game_mode="pvp",
        now=datetime(2026, 10, 6, 0, 0, 0),
    )
    assert dones.list_task_ids(db, user.id, game_mode="pvp") == ["a"]
    assert dones.list_cleared(db, user.id, game_mode="pvp") == []


def test_reset_floor_in_the_future_is_refused() -> None:
    """下限只增不减、撤不回：时钟或时区算错导致的未来下限会让所有设备的日志都写不回来。"""
    db = _session()
    user = _user(db)
    now = datetime(2026, 10, 14, 12, 0, 0)
    kwargs = dict(
        profile_id="aa11",
        reason="prestige",
        epoch=0,
        task_ids=[],
        started_ids=[],
        failed_ids=[],
        objective_dones=[],
        game_mode="pvp",
        now=now,
    )
    with pytest.raises(dones.TarkovTaskDonesError) as exc:
        dones.apply_reset(db, user, reset_at="2026-10-14 20:00:00", **kwargs)
    assert exc.value.status_code == 400
    assert dones.task_boundary(db, user.id, game_mode="pvp")["reset_at"] is None
    # 几分钟的时钟偏差放行
    out = dones.apply_reset(db, user, reset_at="2026-10-14 12:05:00", **kwargs)
    assert out["reset_at"] == "2026-10-14 12:05:00"


def test_concurrent_first_boundary_insert_reuses_the_winner(monkeypatch) -> None:
    """两笔首次写边界同时插行：输的那笔撞主键，吞掉后读到对方已提交的行，不冒成 500。"""
    db = _session()
    user = _user(db)
    dones.clear_progress(db, user, game_mode="pvp", now=T_CLEAR)  # 对方先建好行（epoch 1）
    db.commit()
    # 本请求查存在时对方还没提交：看不到那一行，于是也去插
    monkeypatch.setattr(dones, "_reset_row_exists", lambda *_a: False)
    out = dones.record_profile(db, user, "mine", game_mode="pvp")
    assert out["profile_id"] == "mine"
    assert out["epoch"] == 1  # 用的是对方那一行，不是新插的空行
    assert db.query(TarkovUserTaskReset).count() == 1
    db.commit()
