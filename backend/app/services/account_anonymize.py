"""注销账号：保留 users.id（联机历史外键），清空凭证与可识别资料。"""

from __future__ import annotations

import secrets

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.core.timeutil import now_naive
from app.models.articles import Article, ArticleAuthor
from app.models.job_run import JobRun
from app.models.member import Member
from app.models.register_challenge import RegisterChallenge
from app.models.user import User, UserRole
from app.services.avatar_store import delete_avatar_file, is_custom_avatar_url
from app.services.member_sync import delete_member_cascade

ANONYMIZED_DISPLAY_NAME = "已注销用户"
JOB_KEY = "account_anonymize"


class AccountAnonymizeError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def user_is_anonymized(user: User) -> bool:
    return user.anonymized_at is not None


def anonymize_user_account(
    db: Session,
    user: User,
    *,
    actor_id: int | None,
) -> User:
    """保留 users 行；解绑平台、删草稿与头像。已注销则幂等返回。"""
    if user.anonymized_at is not None:
        return user

    if user.is_admin_user:
        others = (
            db.query(User)
            .filter(
                User.role == UserRole.admin,
                User.id != user.id,
                User.anonymized_at.is_(None),
            )
            .count()
        )
        if others < 1:
            raise AccountAnonymizeError("系统至少保留一名管理员")

    drafts = (
        db.query(Article)
        .filter(Article.author_user_id == user.id, Article.status == "draft")
        .all()
    )
    for row in drafts:
        db.delete(row)

    author = db.query(ArticleAuthor).filter(ArticleAuthor.user_id == user.id).first()
    if author is not None:
        db.delete(author)

    member = db.query(Member).filter(Member.user_id == user.id).first()
    if member is not None:
        if is_custom_avatar_url(member.avatar_url):
            delete_avatar_file(member.id)
        delete_member_cascade(db, member)

    now = now_naive()
    email = (user.email or "").strip().lower()
    if email:
        (
            db.query(RegisterChallenge)
            .filter(RegisterChallenge.email == email)
            .delete(synchronize_session=False)
        )
    user.email = None
    user.email_verified = False
    user.display_name = ANONYMIZED_DISPLAY_NAME
    user.username = f"deleted_{user.id}"
    user.password_hash = hash_password(secrets.token_urlsafe(32))
    user.apply_role(UserRole.user)
    user.anonymized_at = now

    job = JobRun(
        job_key=JOB_KEY,
        status="ok",
        message=f"anonymize user_id={user.id} actor_id={actor_id}",
        stats={"user_id": user.id, "actor_id": actor_id},
        started_at=now,
        finished_at=now,
    )
    db.add(job)
    db.flush()
    return user
