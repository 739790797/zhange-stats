# Alembic 数据库迁移

表结构的**可执行**记录在 `versions/`。应用启动时会自动执行 `upgrade head`；管理端一键更新会在 **`os.execv` 重启前**先跑迁移，失败则回滚代码、不重启，避免生产 502。

MySQL/MariaDB 走 Alembic `upgrade head`（CI `backend-migrate-mariadb` 在 MariaDB 11 上空库跑两遍）。SQLite 首次安装是 ORM `create_all` + `stamp head`，之后与 MySQL 同一套新 migration。

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

SQLite 首次安装走 `create_all` + `stamp head`，之后与 MySQL **同一套** `upgrade head`。新 migration 必须两边都能跑。

1. **幂等**：`ADD COLUMN` / `CREATE TABLE` 前用 `sa.inspect` 判断是否已存在。
2. **禁止 MySQL 专属 DDL**：不要 `CAST(... AS JSON)`、不要 `MODIFY COLUMN` 专供 MySQL。JSON 用 `sa.JSON()`；超 64KB 文本用 `LongText`（`app.core.sqltypes`）。JSON 空值用 `'{}'` 字符串赋值即可。
3. **JSON / 复杂类型改 NULL**：优先可移植 `op.alter_column`，不要写死 MariaDB `MODIFY COLUMN ... JSON`。
4. **修订号唯一**：用日期前缀（如 `20260825_0064`），禁止复用短序号。
5. **SQLite 迁移连接不开外键**：`env.py` 用 `prepare_migration_engine` 让迁移连接保持 `foreign_keys=OFF`（应用引擎是 ON）。batch 模式重建表会 `DROP TABLE`，开着外键会把子表级联删掉；迁移里不要自己打开外键。
6. **时间列默认值**：模型里用 `default=now_naive`（更新时间加 `onupdate=now_naive`），不要 `server_default=func.now()`（SQLite 的 `CURRENT_TIMESTAMP` 是 UTC）。迁移给 NOT NULL 列加库端默认只为回填旧行（`sa.text("CURRENT_TIMESTAMP")` 或常量）。`env.py` 的 `compare_server_default` 钩子：模型已有 Python 默认时不把这类库端默认算漂移；模型声明了库端默认而库里没有，照样报。

改完模型后在 MariaDB 空库上 `alembic upgrade head` 再 `alembic check`，应输出 `No new upgrade operations detected.`。`tests/test_mariadb_migrations.py` 做同样的检查（空库跑两遍、对照模型、北京时间标记、0119 修补），只在设置 `ZHANGE_TEST_MYSQL_URL` 时运行，并会清空该库的全部表，只能指向临时库。

应用内跑迁移（`app.core.migrate`）不按 `alembic.ini` 重配日志，沿用应用自己的 handler；只有命令行 `alembic` 才用 `alembic.ini` 的日志配置。`alembic.ini` 用 `path_separator = os`（Alembic 1.16+ 的键名），`version_locations` 等多路径按系统路径分隔符切分。

## 从旧版 create_all 库升级

若库里已有业务表但没有 `alembic_version`，首次启动会先用 `create_all` + `ensure_schema` 补齐缺表/缺列，再 `stamp` 到当前 head（不会重复执行 baseline 建表）。这类库的时间还是 UTC 口径，会记 `time_storage=utc_pending`，启动时平移成北京墙钟（见 [`docs/database.md`](../../docs/database.md)「时间与默认值」）。

旧版每次 MySQL 启动后跑的修补（`register_challenges` 主键、`minecraft_server_profiles.public_*`）和废弃表 DROP 已不在启动路径上：修补在迁移 `20261010_0119` 里只跑一次，废弃表由 baseline 删除。

**正常已有 alembic_version 的库**：只跑 `upgrade head`，不再执行 `create_all` / `ensure_schema`。新表与列变更必须新增 `versions/` 迁移，并同步 [`docs/database.md`](../../docs/database.md)。
