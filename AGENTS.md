# 战鸽数据 · Agent 入口

战鸽数据（Zhange Stats）提供 Steam 游玩统计、圈子成员、多平台签到与游戏数据功能。技术栈：FastAPI、SQLAlchemy、MySQL/SQLite、APScheduler、React、Ant Design、TanStack Query。

## 开始任何任务

1. 阅读 [`docs/agent-guide.md`](docs/agent-guide.md)，按任务分析、验收与验证流程执行。
2. 阅读 [`docs/engineering-guidelines.md`](docs/engineering-guidelines.md) 及相关领域文档；`docs/` 是项目规范的权威来源。
3. 先检查 `git status` 和目标文件现状，保留与当前任务无关的已有改动，不回滚、不覆盖。
4. 需要时使用 [`docs/agent-skills.md`](docs/agent-skills.md) 索引中的项目专用技能。

## 权威文档

- [`docs/README.md`](docs/README.md)：完整文档索引。
- [`docs/develop.md`](docs/develop.md)、[`docs/deploy.md`](docs/deploy.md)：开发、CI 与部署/发版。
- [`docs/database.md`](docs/database.md)、[`backend/alembic/README.md`](backend/alembic/README.md)：数据库与迁移。
- [`docs/security.md`](docs/security.md)、[`docs/logging.md`](docs/logging.md)：安全、文件管理与运行日志。
- [`docs/directory-layout.md`](docs/directory-layout.md)、[`data/README.md`](data/README.md)：代码分包、运行时目录与上游资源仓。
- [`frontend/src/api/generated/README.md`](frontend/src/api/generated/README.md)：OpenAPI 客户端生成流程。

## 全局约束

- FastAPI 契约变更要同步生成并提交前端 OpenAPI 类型；数据库结构变更要有 Alembic migration，并更新 `docs/database.md`。
- 盒子/旁路 raw 默认读库；签到展示状态打开页必须回源。业务规则见 [`docs/engineering-guidelines.md`](docs/engineering-guidelines.md)。
- 上游仓只由统一同步流程维护；测试使用本地 fixture，不访问真实网络或执行 Git。
- 遵守安全、部署、日志和目录布局文档；不要自行发明与其冲突的约定。

## 高频命令

```bash
# frontend/
npm ci
npm run lint && npm run test && npm run build
npm run export:openapi && npm run gen:api  # 后端 API 契约变化后

# backend/，先激活项目 .venv
python -m pytest -q
ruff check .
alembic revision --autogenerate -m "描述"
alembic upgrade head
```

完整开发环境和质量门见 [`docs/develop.md`](docs/develop.md)；按任务选择测试范围，不要把部分通过报告为全绿。