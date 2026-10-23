# 前端（战鸽数据）

React 18 + Vite 8 + Ant Design 5 + TanStack Query。开发时代理到后端 `http://127.0.0.1:6130`（见 `vite.config.ts`）。需要 Node 22.12+（Vite 8 / vitest 5 的下限）。

## 常用命令

```bash
npm ci                      # openapi-typescript 的 TS peer 由 package.json overrides 指到本仓 typescript，无需 --legacy-peer-deps
npm run dev
npm run lint
npm run test                # vitest：纯函数与组件测试
npm run build
npm run export:openapi      # 从后端导出 OpenAPI（backend/.venv 的 Python，没有则 PATH 上的 python3 / python；加 -- --dry-run 只打印命令）
npm run gen:api             # 生成 src/shared/api/generated/schema.d.ts
node scripts/find-unused-css-modules.mjs   # 只读：列出 *.module.css 里没被引用的类、以及引用了却没定义的类
```

## 目录要点

- `src/app`：启动与 provider 装配、路由/权限/错误边界、全局壳和全局样式。
- `src/features/<domain>`：按业务所有权组织页面、组件、API client/types、hooks、状态、样式、数据与测试；平台和攻略分别归入 `platforms/`、`guides/`。
- `src/shared`：不带具体业务所有权的 HTTP transport、通用 UI/hooks/工具、设计 token、本地化与公共资源；不得依赖 `app/` 或 `features/`。
- 业务 API client 由 owner feature 提供；跨 feature 复用其公开导出，不复制请求实现。所有业务 client 使用 `@/shared/api/http`；OpenAPI 生成物在 `src/shared/api/generated/`。
- feature 专属源码资源（塔科夫地图 JSON、游戏字体等）放在对应 feature 下；运行时/缓存仍在仓库根 `data/`。
- 权威目录与依赖规则见 [`docs/frontend-architecture.md`](../docs/frontend-architecture.md)；跨栈约束见 [`docs/engineering-guidelines.md`](../docs/engineering-guidelines.md)。

## 权限

- `PrivateRoute`：需登录；未登录进登录页并记住回跳路径。
- `AdminRoute`：`isAdminUser`（只信 `role === admin`；`is_admin` 为 API 派生，仅旧缓存缺 role 时回退）；非管理员看 403 页。
- `PlatformRoute`：受 `platform_features` 有效开关控制；关闭时看功能不可用页。
- `/legal/terms`、`/legal/privacy`：公开页，未登录可看（`AuthGuestShell`）。
- `/guides/tarkov`：公开图鉴（`PlatformRoute allowGuest`）；个人中心 / 开房入座在塔科夫壳内提示登录。Minecraft 页面目前停用。
- 页脚 ICP 备案号：`IcpBeianLink`（登录壳、`AppLayout` 主栏、塔科夫正文末尾，随页面滚动；不钉视口），号码来自 `GET /api/settings/site/public`，在管理端「安全设置」配置；留空不展示。
- 未知路径：`NotFoundPage`。
