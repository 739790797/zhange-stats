import pytest
from sqlalchemy import Integer, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.core.security import hash_password, verify_password
from app.core.timeutil import now_naive
from app.models.articles import Article, ArticleAuthor
from app.models.job_run import JobRun
from app.models.member import Member
from app.models.register_challenge import RegisterChallenge
from app.models.tarkov import TarkovRaidRoom, TarkovRaidRoomMember
from app.models.user import User, UserRole
from app.services.account_anonymize import (
    ANONYMIZED_DISPLAY_NAME,
    PERSONAL_TARKOV_MODELS,
    AccountAnonymizeError,
    anonymize_user_account,
)


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _user(db: Session, username: str, *, admin: bool = False, email: str | None = None) -> User:
    row = User(
        username=username,
        email=email,
        display_name=username,
        password_hash=hash_password("correct-horse-battery"),
        role=UserRole.admin if admin else UserRole.user,
        email_verified=True,
    )
    db.add(row)
    db.flush()
    return row


def test_anonymize_clears_identity_and_keeps_id() -> None:
    db = _session()
    user = _user(db, "alice", email="alice@example.com")
    uid = user.id
    member = Member(nickname="alice", user_id=user.id)
    db.add(member)
    db.flush()
    db.add(ArticleAuthor(user_id=user.id))
    draft = Article(
        slug="draft-1",
        title="wip",
        body="x",
        status="draft",
        author_user_id=user.id,
    )
    pub = Article(
        slug="pub-1",
        title="live",
        body="y",
        status="published",
        author_user_id=user.id,
    )
    db.add_all([draft, pub])
    db.commit()

    anonymize_user_account(db, user, actor_id=user.id)
    db.commit()
    db.refresh(user)
    assert user.id == uid
    assert user.email is None
    assert user.display_name == ANONYMIZED_DISPLAY_NAME
    assert user.username == f"deleted_{uid}"
    assert user.anonymized_at is not None
    assert not verify_password("correct-horse-battery", user.password_hash)
    assert db.query(Article).filter(Article.slug == "draft-1").first() is None
    kept = db.query(Article).filter(Article.slug == "pub-1").first()
    assert kept is not None
    assert kept.author_user_id == uid
    assert db.query(Member).filter(Member.user_id == uid).first() is None
    assert db.query(JobRun).filter(JobRun.job_key == "account_anonymize").count() == 1


def test_anonymize_deletes_email_challenges() -> None:
    db = _session()
    _user(db, "other", admin=True, email="a@example.com")
    user = _user(db, "alice", email="alice@example.com")
    db.add(
        RegisterChallenge(
            email="alice@example.com",
            purpose="reset",
            code="123456",
            expires_at=now_naive(),
        )
    )
    db.commit()
    anonymize_user_account(db, user, actor_id=user.id)
    db.commit()
    assert (
        db.query(RegisterChallenge)
        .filter(RegisterChallenge.email == "alice@example.com")
        .count()
        == 0
    )


def test_anonymize_last_admin_rejected() -> None:
    db = _session()
    admin = _user(db, "root", admin=True, email="root@example.com")
    try:
        anonymize_user_account(db, admin, actor_id=admin.id)
        raised = False
    except AccountAnonymizeError:
        raised = True
    assert raised


def test_anonymize_is_idempotent() -> None:
    db = _session()
    _user(db, "other", admin=True, email="a@example.com")
    user = _user(db, "bob", email="b@example.com")
    anonymize_user_account(db, user, actor_id=1)
    db.commit()
    again = anonymize_user_account(db, user, actor_id=1)
    assert again.username == f"deleted_{user.id}"


_FILL = {str: "x", int: 1, dict: {}, object: {}, bool: False}


def _personal_row(model, user_id: int):
    values = {"user_id": user_id}
    for col in model.__table__.columns:
        if col.name in values or col.nullable:
            continue
        if col.default is not None or col.server_default is not None:
            continue
        if col.primary_key and isinstance(col.type, Integer):
            continue
        values[col.name] = _FILL[col.type.python_type]
    return model(**values)


def test_every_tarkov_user_table_is_purged() -> None:
    covered = {model.__tablename__ for model in PERSONAL_TARKOV_MODELS}
    tables = {name for name in Base.metadata.tables if name.startswith("tarkov_user_")}
    assert tables == covered


def test_anonymize_purges_personal_tarkov_data_keeps_room_history() -> None:
    db = _session()
    _user(db, "other", admin=True, email="a@example.com")
    alice = _user(db, "alice", email="alice@example.com")
    bob = _user(db, "bob", email="bob@example.com")
    for model in PERSONAL_TARKOV_MODELS:
        db.add(_personal_row(model, alice.id))
        db.add(_personal_row(model, bob.id))
    room = TarkovRaidRoom(public_id="room1", host_user_id=alice.id, host_display_name="alice")
    db.add(room)
    db.flush()
    db.add(TarkovRaidRoomMember(room_id=room.id, user_id=alice.id, display_name="alice"))
    db.commit()

    anonymize_user_account(db, alice, actor_id=alice.id)
    db.commit()
    for model in PERSONAL_TARKOV_MODELS:
        assert db.query(model).filter(model.user_id == alice.id).count() == 0, model.__tablename__
        assert db.query(model).filter(model.user_id == bob.id).count() == 1, model.__tablename__
    seat = db.query(TarkovRaidRoomMember).filter_by(user_id=alice.id).one()
    assert seat.display_name == ANONYMIZED_DISPLAY_NAME
    assert db.get(TarkovRaidRoom, room.id).host_display_name == ANONYMIZED_DISPLAY_NAME


def test_anonymize_revokes_sessions() -> None:
    db = _session()
    _user(db, "other", admin=True, email="a@example.com")
    user = _user(db, "carol", email="c@example.com")
    assert user.token_version == 0
    anonymize_user_account(db, user, actor_id=user.id)
    db.commit()
    db.refresh(user)
    assert user.token_version == 1


def test_anonymize_admin_race_leaves_an_admin() -> None:
    db = _session()
    a = _user(db, "a", admin=True, email="a@example.com")
    b = _user(db, "b", admin=True, email="b@example.com")
    db.commit()
    # 另一笔请求已把 B 降级并提交
    db.query(User).filter(User.id == b.id).update({User.role: UserRole.user})
    db.commit()
    with pytest.raises(AccountAnonymizeError):
        anonymize_user_account(db, a, actor_id=a.id)
