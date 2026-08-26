# Alembic 数据库迁移

表结构的**可执行**记录在 `versions/`。应用启动时会自动执行 `upgrade head`；管理端一键更新会在 **`os.execv` 重启前**先跑迁移，失败则回滚代码、不重启，避免生产 502。

生产库是 **MariaDB**。CI 的 `backend-migrate-mariadb` 会在 MariaDB 11 上空库 `upgrade head` 两遍，拦住方言不兼容 SQL。

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

## 迁移编写约定（防生产挂死）

MySQL/MariaDB 的 DDL **非事务**：`ADD COLUMN` 成功后若后续语句失败，列已留下但 `alembic_version` 不前进；重启再跑会 `Duplicate column` 死循环。

1. **幂等**：`ADD COLUMN` / `CREATE TABLE` 前用 `sa.inspect` 判断是否已存在。
2. **避免 MySQL 专属写法**：生产是 MariaDB。禁止 `CAST(... AS JSON)`；JSON 空值用 `'{}'` 字符串赋值即可。
3. **JSON / 复杂类型改 NULL**：优先原生 `MODIFY COLUMN ...`，慎用 Alembic `op.alter_column` 对 JSON。
4. **修订号唯一**：用日期前缀（如 `20260825_0064`），禁止复用短序号。

## 从旧版 create_all 库升级

若库里已有业务表但没有 `alembic_version`，首次启动会先用 `create_all` + `ensure_schema` 补齐缺表/缺列，再 `stamp` 到当前 head（不会重复执行 baseline 建表）。

**正常已有 alembic_version 的库**：只跑 `upgrade head`，不再执行 `create_all` / `ensure_schema`。新表与列变更必须新增 `versions/` 迁移，并同步 [`docs/database.md`](../../docs/database.md)。
