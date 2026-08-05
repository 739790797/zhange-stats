# Alembic 数据库迁移

表结构的**可执行**记录在 `versions/`。应用启动时会自动执行 `upgrade head`。

## 日常改表流程

在 `backend/` 目录：

```bash
# 1. 先改 app/models/*.py
# 2. 自动生成迁移（需能连上 DATABASE_URL）
alembic revision --autogenerate -m "add xxx column"

# 3. 人工检查 versions/ 里新文件后提交
# 4. 本地应用
alembic upgrade head
```

其他环境：拉代码后启动应用即可（lifespan 里会 upgrade），或手动：

```bash
alembic upgrade head
alembic current
alembic history
```

## 从旧版 create_all 库升级

若库里已有业务表但没有 `alembic_version`，首次启动会先用 `create_all` + `ensure_schema` 补齐缺表/缺列，再 `stamp` 到当前 head（不会重复执行 baseline 建表）。

**正常已有 alembic_version 的库**：只跑 `upgrade head`，不再执行 `create_all` / `ensure_schema`。新表与列变更必须新增 `versions/` 迁移，并同步根目录 `README.md`「数据库」节。

当前 head：`20260805_0020`（含 `oauth_exchange_tickets`）。
