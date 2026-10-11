import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.timeutil import now_naive


class UserRole(str, enum.Enum):
    user = "user"
    admin = "admin"


class User(Base):
    __tablename__ = "users"
    # SQLite 默认会把删掉的最大 id 再发给下一行；令牌、Cookie、缓存都按 id 认人，新建库用 AUTOINCREMENT
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    email: Mapped[str | None] = mapped_column(String(128), unique=True, index=True, nullable=True)
    display_name: Mapped[str] = mapped_column(String(64), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=UserRole.user,
    )
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    anonymized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # 写进 JWT 的 ver；改密 / 重置 / 降级 / 注销 / 退出所有设备时 +1，旧令牌即失效
    token_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=now_naive,
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False,
    )

    member = relationship(
        "Member",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @property
    def is_admin_user(self) -> bool:
        """权限唯一入口：仅看 role（API 的 is_admin 字段由此派生）。"""
        return self.role == UserRole.admin

    def apply_role(self, role: UserRole) -> None:
        self.role = role
