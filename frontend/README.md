# 前端（战鸽数据）

React 18 + Vite 8 + Ant Design 5 + TanStack Query。开发时代理到后端 `http://127.0.0.1:6130`（见 `vite.config.ts`）。

## 常用命令

```bash
npm ci --legacy-peer-deps   # 因 openapi-typescript 与 TS 6 peer 冲突
npm run dev
npm run lint
npm run test                # vitest：lib / 展示纯函数
npm run build
npm run export:openapi      # 从后端导出 OpenAPI
npm run gen:api             # 生成 src/api/generated/schema.d.ts
```

## 目录要点

- `src/pages`：路由页
- `src/components`：根上跨平台外壳；平台面板在 `skland/` `mihoyo/` 等子目录；攻略在 `guides/`
- `src/data`：源码资源（塔科夫地图 JSON 等）；运行时/缓存在仓库根 `var/`
- `src/api`：axios + 按域 `*Api`；业务类型几乎均从 `generated/schema.d.ts` 派生；`formatDuration` 等工具仍在 `types.ts`
- `src/lib/apiError` / `formatRequestError`：统一错误文案；`npm run test`（vitest）覆盖 `lib/` 与组件旁纯函数（见 `testing.mdc`）
- `src/stores/authStore.ts`：仅存 JWT + 用户（localStorage）
- 约定：仓库根 `AGENTS.md`；Cursor 规则 `frontend-conventions` / `frontend-api-errors` / `testing`

## 权限

- `PrivateRoute`：需登录；未登录进登录页并记住回跳路径
- `AdminRoute`：`role === admin`（或派生 `is_admin`）；非管理员看 403 页
- `PlatformRoute`：受 `platform_features` 有效开关控制；关闭时看功能不可用页
- 未知路径：`NotFoundPage`
