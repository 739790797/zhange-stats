---
name: zhange-upstream-data-change
description: 修改上游资源仓、外部数据同步、raw 缓存、解析或刷新策略时使用。
---

# Zhange Upstream Data Change

## 触发条件

改动 `data/repos/` 生命周期、外部 API 拉取、定时同步、图鉴/养成盒 raw、资源解析、上游失败回退或相关测试时使用。

## 必要步骤

1. 阅读 [`data/README.md`](../../../data/README.md)、[工程约定](../../../docs/engineering-guidelines.md) 和 [开发/部署说明](../../../docs/develop.md)，确认资源仓登记、路径、计划任务、备份与文件管理边界。
2. 检查 `backend/app/services/upstream_repos.py` 及目标域现有 client/pipeline。复用统一浅克隆和更新流程；读请求只解析登记的本地仓，不按请求运行 Git，也不新增逐文件 raw URL 下载路径。
3. 明确原始数据的权威来源、解析纯度、缓存/`force`/stale 语义和失败行为。同步失败时保留最后一份可用 checkout/raw；不完整来源或公式保持未知，不猜测补齐。
4. 测试只用本地 fixture、临时目录和注入的 Git runner；禁止 pytest 访问真实上游网络、GitHub 或执行 Git。
5. 视变更补齐任务注册/时间、缺仓提示、OpenAPI 生成、数据目录与同步说明；旧仓是否仍可读和备份范围要回归验证。

## 验收与停止条件

- 正常、缺数据和失败路径均有确定行为；失败不会删除或覆盖已有有效数据。
- 定向测试不依赖网络、不访问开发者机器上的 checkout，也不调用真实 Git。
- 若源数据许可/结构、数据可信度或保留策略不明，停止猜测，记录缺口并请求确认。

## 权威文档

- [运行时数据与上游仓](../../../data/README.md)
- [工程约定与平台数据语义](../../../docs/engineering-guidelines.md)
- [安全与资源 API 行为](../../../docs/security.md)
- [开发及部署任务](../../../docs/develop.md) · [部署与发版](../../../docs/deploy.md)