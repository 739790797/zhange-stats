---
name: zhange-api-change
description: 变更 FastAPI 路由或 schema、OpenAPI 契约、前端 API client/types 或跨栈行为时使用。
---

# Zhange API Change

## 触发条件

改动影响 FastAPI endpoint/schema、前后端 API 契约、认证/错误语义、生成类型，或需要贯通服务端与前端行为时使用。

## 必要步骤

1. 阅读 [Agent 工作流程](../../../docs/agent-guide.md) 与 [工程约定](../../../docs/engineering-guidelines.md)，检查工作区现有改动和相关调用链。
2. 明确验收行为与影响层；按需要检查 service → schema → route → `frontend/src/api/*Api.ts` → client/types → page/component。
3. 后端契约发生变化时，在 `frontend/` 运行 `npm run export:openapi && npm run gen:api`，检查并保留生成的 `generated/` diff；不要只手改类型。
4. 在实现规则的层补定向测试。涉及表结构时，改走 Alembic migration 并更新 `docs/database.md`。
5. 复核鉴权、错误处理、`force` 默认值和兼容性；只修改任务范围内文件。

## 验收与停止条件

- 行为、错误/权限语义与验收项一致；涉及契约的 OpenAPI JSON 与类型已重新生成。
- 相关定向测试通过，或明确记录受环境/基线阻断的检查；完整结果按 [Agent 工作流程](../../../docs/agent-guide.md) 报告。
- 若 API 语义、授权策略、数据库迁移或上游数据可信度尚未明确，先停止扩展实现并说明需要确定的决策，不猜测契约。

## 权威文档

- [工程约定](../../../docs/engineering-guidelines.md)
- [数据库表结构与迁移](../../../docs/database.md)
- [生成 API 说明](../../../frontend/src/api/generated/README.md)
- [安全规范](../../../docs/security.md)