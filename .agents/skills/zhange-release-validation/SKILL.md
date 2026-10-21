---
name: zhange-release-validation
description: 为代码变更、交付或发版选择并执行测试与质量门，或报告验证结果时使用。
---

# Zhange Release Validation

## 触发条件

用户要求测试、质量核验、交付审查、发版准备，或需要为本次实现确定验证范围时使用。

## 必要步骤

1. 阅读 [Agent 工作流程](../../../docs/agent-guide.md)、[开发与 CI 质量门](../../../docs/develop.md)；发版任务另读 [部署/发版说明](../../../docs/deploy.md)。
2. 检查当前 `git status`、完整 diff 与改动层，保留已有未提交内容；按风险选择定向测试，必要时再跑全量门禁。
3. 验证配套项：API 变更有 OpenAPI 导出/生成物；表结构变更有 migration 与 `docs/database.md`；配置模板变更更新 `_version`；相关文档/文件链接有效。
4. 对失败逐项确认是本次改动、既有基线还是环境问题。记录原始命令、退出状态、通过/失败/跳过数量和能复现的失败信息。
5. 最终报告区分定向检查、完整套件、CI/发版门禁；没有执行的检查标为未运行，不推断通过。

## 验收与停止条件

- 相关检查真实执行，产物/生成物/diff 经检查；结论有命令与证据支撑。
- 若环境阻止验证，或失败来源尚不能归因，停止宣称通过，保留不确定性并说明下一步。
- 文档/Agent 配置专属变更通常验证链接、frontmatter、diff 与 `git diff --check` 即可；不要无故运行无关的产品测试。

## 权威文档

- [Agent 工作流程与结果报告](../../../docs/agent-guide.md)
- [CI 与质量门](../../../docs/develop.md)
- [发版流程](../../../docs/deploy.md)
- [OpenAPI 生成物](../../../frontend/src/api/generated/README.md)
- [数据库迁移](../../../backend/alembic/README.md)