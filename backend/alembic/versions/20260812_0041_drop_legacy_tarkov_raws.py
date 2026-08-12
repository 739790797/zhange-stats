"""Drop leftover tarkov ammo/gun raw tables if present.

Revision ID: 20260812_0041
Revises: 20260812_0040
Create Date: 2026-08-12

兼容：0040 已应用后若为旧进程临时重建了 ammo/gun raws，部署新代码后清理。
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260812_0041"
down_revision: Union[str, Sequence[str], None] = "20260812_0040"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = set(inspector.get_table_names())
    if "tarkov_gun_raws" in tables:
        op.drop_table("tarkov_gun_raws")
    if "tarkov_ammo_raws" in tables:
        op.drop_table("tarkov_ammo_raws")


def downgrade() -> None:
    # 不重建旧分表；共享 items raw 已是唯一来源
    pass
