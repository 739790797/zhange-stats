"""用户与成员同步：启动修复返回的统计要如实反映补齐 / 改名 / 清孤儿。"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.core.database import Base
from app.models.member import Member
from app.models.user import User
from app.services.member_sync import sync_users_and_members


def _user(db, username: str, display_name: str) -> User:
    row = User(username=username, display_name=display_name, password_hash="x")
    db.add(row)
    db.flush()
    return row


def test_sync_counts_created_renamed_and_orphan_members() -> None:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, autoflush=False)()
    renamed = _user(db, "renamed", "新名字")
    db.add(Member(nickname="旧名字", user_id=renamed.id))
    same = _user(db, "same", "不变")
    db.add(Member(nickname="不变", user_id=same.id))
    _user(db, "fresh", "新人")
    db.add(Member(nickname="孤儿", user_id=None))
    db.commit()

    stats = sync_users_and_members(db)

    assert stats == {"created": 1, "synced": 1, "removed": 1}
    names = sorted(m.nickname for m in db.query(Member).all())
    assert names == ["不变", "新人", "新名字"]
    db.close()
    engine.dispose()
