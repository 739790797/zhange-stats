from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base
from app.core.security import hash_password, verify_password
from app.core.timeutil import now_naive
from app.models.articles import Article, ArticleAuthor
from app.models.job_run import JobRun
from app.models.member import Member
from app.models.register_challenge import RegisterChallenge
from app.models.user import User, UserRole
from app.services.account_anonymize import (
    ANONYMIZED_DISPLAY_NAME,
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
