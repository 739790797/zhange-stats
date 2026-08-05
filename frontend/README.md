# 前端（战鸽数据）

React 18 + Vite 8 + Ant Design 5 + TanStack Query。开发时代理到后端 `http://127.0.0.1:8000`（见 `vite.config.ts`）。

## 常用命令

```bash
npm ci --legacy-peer-deps   # 因 openapi-typescript 与 TS 6 peer 冲突
npm run dev
npm run lint
npm run build
npm run export:openapi      # 从后端导出 OpenAPI
npm run gen:api             # 生成 src/api/generated/schema.d.ts
```

## 目录要点

- `src/pages`：路由页
- `src/api`：axios + 按域 `*Api`；业务类型几乎均从 `generated/schema.d.ts` 派生；`formatDuration` 等工具仍在 `types.ts`
- `src/lib/apiError` / `formatRequestError`：统一错误文案；`npm run test`（vitest）覆盖解析逻辑
- `src/stores/authStore.ts`：仅存 JWT + 用户（localStorage）
- 约定：仓库根 `AGENTS.md`；Cursor 规则 `frontend-conventions` / `frontend-api-errors`

## 权限

- `PrivateRoute`：需登录
- `AdminRoute`：`role === admin`（或派生 `is_admin`）
- `PlatformRoute`：受 `platform_features` 有效开关控制
