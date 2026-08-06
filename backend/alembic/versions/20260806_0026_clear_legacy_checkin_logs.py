"""Clear legacy checkin logs and bind last_checkin summaries.

新编排仍使用 *_checkin_logs / last_checkin_* 表结构，本迁移只清数据：
生产与本地 upgrade 后，打开签到页会按新流程回源重写今日日志。

Revision ID: 20260806_0026
Revises: 20260806_0025
Create Date: 2026-08-06

"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260806_0026"
down_revision: Union[str, Sequence[str], None] = "20260806_0025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_LOG_TABLES = (
    "skland_checkin_logs",
    "taygedo_checkin_logs",
    "exilium_checkin_logs",
    "kujiequ_checkin_logs",
)

_BIND_TABLES = (
    "skland_binds",
    "taygedo_binds",
    "exilium_binds",
    "kujiequ_binds",
)


def upgrade() -> None:
    for table in _LOG_TABLES:
        op.execute(sa.text(f"DELETE FROM `{table}`"))

    for table in _BIND_TABLES:
        op.execute(
            sa.text(
                f"UPDATE `{table}` SET "
                "last_checkin_at=NULL, "
                "last_checkin_date=NULL, "
                "last_checkin_summary=NULL, "
                "last_checkin_ok=NULL"
            )
        )


def downgrade() -> None:
    # 已删除的历史签到行无法恢复
    pass
