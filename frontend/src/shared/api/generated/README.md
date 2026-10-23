# 自动生成的 API 类型

本目录由后端 OpenAPI 规范自动生成，请勿手动编辑 `openapi.json` 与 `schema.d.ts`。

## 重新生成

在仓库根目录或按下列顺序执行：

1. `npm run export:openapi`（在 `frontend/` 执行，调用后端 `scripts/export_openapi.py`）
2. `npm run gen:api`（生成本目录中的 `schema.d.ts`）

后端 API 变更后请更新本目录并提交，否则 CI 的 **openapi-drift** 任务会失败。

## 与手写类型的关系

**契约源是本目录的 `schema.d.ts`。** 各 owner feature 的 `api/types.ts` 与业务 API client 类型（含 settings / setup）应派生自 `components["schemas"]`；页面本地 FormValues 可手写。
