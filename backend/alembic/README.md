# Alembic

迁移目录预留。当前使用 `Base.metadata.create_all` 与 `ensure_schema` 处理建表与废弃表清理。

后续可接入：

```bash
alembic init alembic
alembic revision --autogenerate -m "init"
alembic upgrade head
```
