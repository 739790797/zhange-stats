# 战鸽数据 · 文档与 Agent 规范

`docs/` 是项目流程与工程规范的权威来源；本文是索引，不重复正文。根 [`AGENTS.md`](../AGENTS.md) 是自动加载的精简入口，包含 Agent 开始工作的指引。

## Agent 与 Skills

| 入口 | 内容 |
|---|---|
| [`agent-guide.md`](agent-guide.md) | 任务拆解、验收标准、委派边界、测试分层与结果报告；可选 MCP 手动设置 |
| [`engineering-guidelines.md`](engineering-guidelines.md) | 后端/前端约定、API 契约、签到/raw、平台数据与测试边界 |
| [`agent-skills.md`](agent-skills.md) | 三个项目专用 Skills 与外部 Agent Skills 上游插件的固定版本/注册方法 |
| [`.agents/skills/`](../.agents/skills/) | Agent 可发现的项目专用 Skills |

按主题继续阅读以下文档；没有专用文档的项目实现约束集中在 `engineering-guidelines.md`。

## 开发、部署与运行

| 主题 | 文档 |
|---|---|
| 技术栈、本地开发、依赖与 CI 质量门 | [`develop.md`](develop.md) |
| 安装、升级、备份、恢复、发版与公开运营检查 | [`deploy.md`](deploy.md) |
| 表结构总览、迁移要求 | [`database.md`](database.md)、[`backend/alembic/README.md`](../backend/alembic/README.md) |
| 安全、鉴权、Cookie/CSRF、文件管理、上传、限流与权限 | [`security.md`](security.md) |
| 运行日志级别、禁刷规则、日志管道 | [`logging.md`](logging.md) |
| 目录结构与代码分包 | [`directory-layout.md`](directory-layout.md)、[`frontend-architecture.md`](frontend-architecture.md) |
| 硬化路线历史与落地记录 | [`hardening-roadmap.md`](hardening-roadmap.md) |
| 运行时数据目录、上游资源仓同步、备份范围 | [`data/README.md`](../data/README.md) |

## 按任务快速定位

| 任务 | 阅读 |
|---|---|
| 改 API 或跨栈契约 | [`zhange-api-change`](../.agents/skills/zhange-api-change/SKILL.md)、[`engineering-guidelines.md`](engineering-guidelines.md)、[`frontend/src/shared/api/generated/README.md`](../frontend/src/shared/api/generated/README.md) |
| 改上游资源、缓存或同步任务 | [`zhange-upstream-data-change`](../.agents/skills/zhange-upstream-data-change/SKILL.md)、[`data/README.md`](../data/README.md)、[`engineering-guidelines.md`](engineering-guidelines.md) |
| 测试、质量门或发版前验证 | [`zhange-release-validation`](../.agents/skills/zhange-release-validation/SKILL.md)、[`agent-guide.md`](agent-guide.md)、[`develop.md`](develop.md)、[`deploy.md`](deploy.md) |
| 改表或迁移 | [`database.md`](database.md)、[`backend/alembic/README.md`](../backend/alembic/README.md) |
| 安全、文件管理、签到/游戏权限 | [`security.md`](security.md)、[`engineering-guidelines.md`](engineering-guidelines.md) |
| 日志或代码分包 | [`logging.md`](logging.md)、[`directory-layout.md`](directory-layout.md) |
| 雨中冒险 2 列表与新增目录页 | [ROR2 列表规则](ror2-list-rules.md) |

## 根目录与就地 README

- 根 [`README.md`](../README.md)：项目介绍、功能摘要与致谢。
- 根 [`AGENTS.md`](../AGENTS.md)：Agent 自动加载入口。
- [`frontend/README.md`](../frontend/README.md)：前端命令与路由权限。
- [`frontend-architecture.md`](frontend-architecture.md)：前端 feature-first 目录所有权与依赖规则。
- [`frontend/src/shared/api/generated/README.md`](../frontend/src/shared/api/generated/README.md)：OpenAPI 生成物说明。
- [`backend/alembic/README.md`](../backend/alembic/README.md)：迁移流程与旧库处理。
- [`backend/local_dev/README.md`](../backend/local_dev/README.md)：本地假 Steam 数据 CLI。
- [`data/README.md`](../data/README.md)：运行时数据目录。

## 非规范类常用文件

| 路径 | 用途 |
|---|---|
| `scripts/config.example/` | 站点配置模板；字段变化要递增 `_version`，真实 `config/` 不入库 |
| `VERSION` | 发版号；以质量门通过后的 GitHub Release 为准 |
| `scripts/linux/`、`scripts/win/` | 安装、运行、重启、更新、备份、恢复脚本 |
| `scripts/common/` | 跨平台更新、备份与本机数据库准备逻辑 |