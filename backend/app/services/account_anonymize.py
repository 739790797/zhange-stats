"""注销账号：保留 users.id（联机历史外键），清空凭证与可识别资料。"""

from __future__ import annotations

import secrets

from sqlalchemy.orm import Session

from app.core.security import bump_token_version, hash_password
from app.core.timeutil import now_naive
from app.models.articles import Article, ArticleAuthor
from app.models.job_run import JobRun
from app.models.member import Member
from app.models.register_challenge import RegisterChallenge
from app.models.tarkov import (
    TarkovRaidRoom,
    TarkovRaidRoomMember,
    TarkovUserCollectionLayout,
    TarkovUserCollectionOwn,
    TarkovUserCollectionPlacement,
    TarkovUserHideoutLevel,
    TarkovUserKeyOwn,
    TarkovUserMapFilter,
    TarkovUserProfile,
    TarkovUserRaidLog,
    TarkovUserRaidPrep,
    TarkovUserTaskDone,
    TarkovUserTaskFailed,
    TarkovUserTaskObjectiveDone,
    TarkovUserTaskStarted,
)
from app.models.user import User, UserRole
from app.services.auth_config import admins_remaining, lock_admin_ids
from app.services.avatar_store import delete_avatar_file, is_custom_avatar_url
from app.services.member_sync import delete_member_cascade

ANONYMIZED_DISPLAY_NAME = "已注销用户"
JOB_KEY = "account_anonymize"

# 只删纯个人的塔科夫进度 / 偏好 / 对局记录；联机房间里的成员、标记、钥匙等行留给房间历史，靠 users.id 保留关联
PERSONAL_TARKOV_MODELS = (
    TarkovUserTaskDone,
    TarkovUserTaskFailed,
    TarkovUserTaskStarted,
    TarkovUserTaskObjectiveDone,
    TarkovUserKeyOwn,
    TarkovUserCollectionOwn,
    TarkovUserCollectionLayout,
    TarkovUserCollectionPlacement,
    TarkovUserProfile,
    TarkovUserMapFilter,
    TarkovUserHideoutLevel,
    TarkovUserRaidLog,
    TarkovUserRaidPrep,
)


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

    was_admin = user.is_admin_user
    if was_admin:
        others = [uid for uid in lock_admin_ids(db) if uid != user.id]
        if not others:
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
            delete_avatar_file(member.id, db=db)
        delete_member_cascade(db, member)

    for model in PERSONAL_TARKOV_MODELS:
        db.query(model).filter(model.user_id == user.id).delete(
            synchronize_session=False
        )
    # 房间行入座时抄了一份显示名，历史留着但名字换掉
    db.query(TarkovRaidRoomMember).filter(TarkovRaidRoomMember.user_id == user.id).update(
        {TarkovRaidRoomMember.display_name: ANONYMIZED_DISPLAY_NAME},
        synchronize_session=False,
    )
    db.query(TarkovRaidRoom).filter(TarkovRaidRoom.host_user_id == user.id).update(
        {TarkovRaidRoom.host_display_name: ANONYMIZED_DISPLAY_NAME},
        synchronize_session=False,
    )

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
    bump_token_version(user)
    if was_admin and admins_remaining(db) < 1:
        raise AccountAnonymizeError("系统至少保留一名管理员")

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
