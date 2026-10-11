"""Steam 轮询：单个成员写库失败不连累其他人；商店名在循环前一次解析；失败回写 job_runs。"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.models.job_run import JobRun
from app.models.member import Member
from app.models.play_session import PlaySession
from app.models.presence_segment import PresenceSegment
from app.services.adapters.steam import SteamPresence
from app.services.steam import poller


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _playing(steam_id: str, app_id: str = "730") -> SteamPresence:
    return SteamPresence(
        steam_id=steam_id,
        persona_name=f"p{steam_id}",
        persona_state=1,
        game_id=app_id,
        game_extra_info="Counter-Strike 2",
    )


def _wire(monkeypatch, presences: list[SteamPresence], *, fail_fetch: bool = False) -> list:
    name_calls: list[list[str]] = []

    class FakeAdapter:
        def __init__(self, key: str) -> None:
            assert key == "k"

        def fetch_summaries(self, steam_ids):
            if fail_fetch:
                raise RuntimeError("steam api down")
            return {"ids": list(steam_ids)}

        def parse_presences(self, raw):
            return [p for p in presences if p.steam_id in raw["ids"]]

    def fake_names(_db, app_ids, **_k):
        name_calls.append(sorted(app_ids))
        return {"730": "反恐精英2"}

    monkeypatch.setattr("app.services.integrations_config.get_steam_api_key", lambda _db: "k")
    monkeypatch.setattr("app.services.scheduler_config.load_scheduler_config", lambda _db: {})
    monkeypatch.setattr(poller, "SteamAdapter", FakeAdapter)
    monkeypatch.setattr(poller, "resolve_app_names", fake_names)
    return name_calls


def test_one_member_failure_keeps_others(monkeypatch) -> None:
    db = _session()
    bad = Member(nickname="bad", steam_id="1")
    good = Member(nickname="good", steam_id="2")
    db.add_all([bad, good])
    db.commit()
    bad_id, good_id = bad.id, good.id
    name_calls = _wire(monkeypatch, [_playing("1"), _playing("2")])

    def persona(member, name, *, avatar_url=None):
        if member.steam_id == "1":
            raise RuntimeError("boom")
        return False

    monkeypatch.setattr(poller, "apply_steam_persona_name", persona)

    out = poller.run_steam_presence_poll(db)

    assert out["status"] == "error"
    assert out["stats"]["failed"] == 1
    assert "失败 1 人" in out["message"]
    assert name_calls == [["730", "730"]]
    segs = db.query(PresenceSegment).all()
    assert [(s.member_id, s.game_name) for s in segs] == [(good_id, "反恐精英2")]
    plays = db.query(PlaySession).all()
    assert [p.member_id for p in plays] == [good_id]
    assert bad_id not in {s.member_id for s in segs}
    job = db.query(JobRun).one()
    assert job.status == "error"
    assert job.finished_at is not None


def test_second_poll_continues_open_rows(monkeypatch) -> None:
    db = _session()
    db.add(Member(nickname="a", steam_id="1"))
    db.commit()
    _wire(monkeypatch, [_playing("1")])
    monkeypatch.setattr(poller, "apply_steam_persona_name", lambda *a, **k: False)

    first = poller.run_steam_presence_poll(db)
    second = poller.run_steam_presence_poll(db)

    assert first["status"] == "ok"
    assert second["stats"]["presence_continued"] == 1
    assert second["stats"]["continued"] == 1
    assert db.query(PresenceSegment).count() == 1
    assert db.query(PlaySession).filter(PlaySession.ended_at.is_(None)).count() == 1


def test_fetch_failure_is_written_back_to_job_run(monkeypatch) -> None:
    db = _session()
    db.add(Member(nickname="a", steam_id="1"))
    db.commit()
    _wire(monkeypatch, [], fail_fetch=True)

    out = poller.run_steam_presence_poll(db)

    assert out["status"] == "error"
    assert out["message"] == "steam api down"
    job = db.query(JobRun).one()
    assert job.status == "error"
    assert job.message == "steam api down"
    assert job.finished_at is not None
