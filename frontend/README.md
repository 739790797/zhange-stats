# 前端（战鸽数据）

React 18 + Vite 8 + Ant Design 5 + TanStack Query。开发时代理到后端 `http://127.0.0.1:6130`（见 `vite.config.ts`）。需要 Node 22.12+（Vite 8 / vitest 5 的下限）。

## 常用命令

```bash
npm ci                      # openapi-typescript 的 TS peer 由 package.json overrides 指到本仓 typescript，无需 --legacy-peer-deps
npm run dev
npm run lint
npm run test                # vitest：lib / 展示纯函数
npm run build
npm run export:openapi      # 从后端导出 OpenAPI（backend/.venv 的 Python，没有则 PATH 上的 python3 / python；加 -- --dry-run 只打印命令）
npm run gen:api             # 生成 src/api/generated/schema.d.ts
node scripts/find-unused-css-modules.mjs   # 只读：列出 *.module.css 里没被引用的类、以及引用了却没定义的类
```

## 目录要点

- `src/pages`：路由页
- `src/components`：根上跨平台外壳；平台面板在 `skland/` `mihoyo/` 等子目录；攻略在 `guides/`
- `src/data`：源码资源（塔科夫地图 JSON 等）；运行时/缓存在仓库根 `data/`
- `src/api`：axios + 按域 `*Api`；业务类型几乎均从 `generated/schema.d.ts` 派生；`formatDuration` 等工具仍在 `types.ts`
- `src/lib/apiError`：用户可见错误文案（内部走 `formatRequestError`）；`npm run test`（vitest）覆盖 `lib/` 与组件旁纯函数（见 `testing.mdc`）
- `src/stores/authStore.ts`：只持久化 `user`（登录态以 HttpOnly Cookie 为准）
- 约定：仓库根 `AGENTS.md`；Cursor 规则 `frontend-conventions` / `frontend-api-errors` / `testing`

## 权限

- `PrivateRoute`：需登录；未登录进登录页并记住回跳路径
- `AdminRoute`：`isAdminUser`（只信 `role === admin`；`is_admin` 为 API 派生，仅旧缓存缺 role 时回退）；非管理员看 403 页
- `PlatformRoute`：受 `platform_features` 有效开关控制；关闭时看功能不可用页
- `/legal/terms`、`/legal/privacy`：公开页，未登录可看（`AuthGuestShell`）
- `/guides/tarkov`：公开图鉴（`PlatformRoute allowGuest`）；个人中心 / 开房入座在塔科夫壳内提示登录。Minecraft 仍 `PrivateRoute`
- 页脚 ICP 备案号：`IcpBeianLink`（登录壳、`AppLayout` 主栏、塔科夫正文末尾，随页面滚动；不钉视口），号码来自 `GET /api/settings/site/public`，在管理端「安全设置」配置；留空不展示
- 未知路径：`NotFoundPage`
