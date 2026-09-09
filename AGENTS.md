# 战鸽数据 · Agent 指南

战鸽数据（Zhange Stats）：Steam 游玩统计 + 圈子成员 + 多平台签到/盒子。  
栈：FastAPI + MySQL + APScheduler · React + Ant Design + TanStack Query。

人读文档总目录：[`docs/README.md`](docs/README.md)（不搬家，只做索引）。

## 改代码前必读

| 文档 | 用途 |
|------|------|
| [`docs/README.md`](docs/README.md) | 全仓库文档索引 |
| [`.cursor/mcp.json`](.cursor/mcp.json) | Cursor 项目 MCP（Ant Design 5 / Context7 / Playwright） |
| [`.cursor/rules/zhange-architecture.mdc`](.cursor/rules/zhange-architecture.mdc) | 架构索引（Agent always-on） |
| [`.cursor/rules/platform-raw-cache.mdc`](.cursor/rules/platform-raw-cache.mdc) | 盒子 / 旁路 raw / 签到今日 logs |
| [`.cursor/rules/skland-upstream.mdc`](.cursor/rules/skland-upstream.mdc) | 森空岛官服/B服、补奖、cred、渠道测 |
| [`.cursor/rules/tarkov-upstream.mdc`](.cursor/rules/tarkov-upstream.mdc) | 塔科夫图鉴只走 json.tarkov.dev，不打 GraphQL |
| [`.cursor/rules/db-schema-readme.mdc`](.cursor/rules/db-schema-readme.mdc) | Alembic + `docs/database.md` 表结构 |
| [`.cursor/rules/frontend-conventions.mdc`](.cursor/rules/frontend-conventions.mdc) | 前端约定（含 status `force` 显式传参） |
| [`.cursor/rules/frontend-ui.mdc`](.cursor/rules/frontend-ui.mdc) | Ant Design 主题、按钮角色/尺寸 |
| [`.cursor/rules/backend-conventions.mdc`](.cursor/rules/backend-conventions.mdc) | 后端约定（含 Adapter checklist / 可选钩子） |
| [`.cursor/rules/logging.mdc`](.cursor/rules/logging.mdc) | 运行时日志（级别 / 禁刷）；全文 [`docs/logging.md`](docs/logging.md) |
| [`.cursor/rules/testing.mdc`](.cursor/rules/testing.mdc) | 自测分层、补测门槛、禁止同层重复 |
| [`.cursor/rules/frontend-api-errors.mdc`](.cursor/rules/frontend-api-errors.mdc) | `apiError` / `*Api` 边界 |
| [`.cursor/rules/directory-layout.mdc`](.cursor/rules/directory-layout.mdc) | 新平台进 `services/<域>` / `components/<域>` |
| [`docs/directory-layout.md`](docs/directory-layout.md) | 目录结构全文（`var/`、分包映射） |
| [`docs/agent-governance-plan.md`](docs/agent-governance-plan.md) | 治理方案（已落地） |
| 根 [`README.md`](README.md) | 站点性质、功能概要、致谢 |
| [`docs/develop.md`](docs/develop.md) | 本地开发 |
| [`docs/deploy.md`](docs/deploy.md) | 生产部署 |
| [`docs/database.md`](docs/database.md) | 表结构总览 |
| [`docs/security.md`](docs/security.md) | 安全与运行注意 |
| [`docs/logging.md`](docs/logging.md) | 运行时日志规范（平台日志；非签到库表） |

## 高频命令

```bash
# 前端（frontend/）
npm ci --legacy-peer-deps
npm run dev
npm run lint && npm run test && npm run build
npm run export:openapi && npm run gen:api   # 改后端 API 后必做

# 本机生命周期（每边五件套；不区分生产/开发）
# Windows: scripts/win/install.ps1 · run.ps1 · restart.ps1 · backup.ps1 · restore.ps1
# Linux:   sudo bash scripts/linux/install.sh · run.sh · restart.sh · backup.sh · restore.sh

# 后端（backend/，激活 .venv）
python -m pytest -q
alembic revision --autogenerate -m "..."
alembic upgrade head
```

## 禁止清单

- 无 Alembic 改表；往 `schema_ensure.py` 堆新 `ALTER`
- 签到 status 写 `bind.last_checkin_*`；签到展示打开页不 force 回源；用户侧展示执行记录
- 新签到平台复制整份 `*_checkin` 编排（应实现 Adapter + 注册表）
- 新平台签到/兑换页不套 `CheckinPageTemplate` / `ExchangePageTemplate` / `PlatformFeatureTabsPage`
- 新管理子页不进 `AdminHubLayout`、往侧栏再堆叶子（站点设置 / 运行维护 / 任务管理 / 用户管理共用 wide 栏）
- 新签到日历复制整份 Modal；新盒子复制 loading/刷新条；扫码绑定复制 start/poll 定时器（应走 `AttendanceCalendarButton` / `BoxPanelChrome` / `useQrBindSession`）
- Button 内联 `#1a2332` 锁死主色；主应用引入第二套 UI 库或抄塔科夫暗色主题
- 森空岛：B服 GET 空 records 当未签；attendance `gameId` 回退官服 `1`；B服 already 后再 GET 补奖
- 塔科夫图鉴回源 `api.tarkov.dev` GraphQL（应走 json.tarkov.dev dump）
- 塔科夫联机：非成员 `GET` 房间回完整棋盘（应只给预览：标题/地图/人数/是否要密码等，无棋盘）；房间码当秘密
- `fetch*Status` 用 `...(force ? { force: true } : {})` 省略 force（与后端默认 true 错位）
- 页面直连 axios / 手拆 `e.response.data.detail`（用 `apiError`）
- 只改手写 `types.ts` 冒充 API 契约（应走 OpenAPI → `schema.d.ts`）
- 去掉 CSRF / 登出清 Cookie / 生产 CORS 收紧，却只把 JWT 改成可读 Cookie 或继续 persist JWT
- 生产开启 `ALLOW_EMAIL_CODE_LOG`（启动硬拒绝）；生产使用默认弱 `ADMIN_PASSWORD`
- 文件管理把查询参数当任意绝对路径读盘；把 `.secret_key` / `.env` / `.git` / 备份 `zhange-*.tar.gz` 当普通文件下发或进入
- 新业务用户上传直写 `UPLOAD_DIR`（应走 `services/user_files` + namespace；头像覆盖写也要登记）
- 应用进程内 apt / winget 装 MariaDB（走 `scripts/common/provision_mariadb.py`；Windows 便携包在 `var/mariadb/`）
- 脚本用参数区分生产/开发，或做生产库同步到开发库 / curl 应急覆盖源码（公开入口只有 install / run / restart / backup / restore；环境只看该安装树 `.env`）
- 成功快 GET / 健康与日志轮询打 INFO；循环内逐条 INFO；密钥、验证码、Cookie 进日志
- 质量门红时当已发版、手工打 tag，或改 `VERSION` 却不打算让生产看见新版本

## PR 自检

- [ ] 改 API：已 `export:openapi && gen:api`，generated 有 diff
- [ ] 改模型：有 Alembic + `docs/database.md`
- [ ] 改签到/盒子：盒子符合 raw 读库优先；签到展示始终 force 回源、不展示执行记录
- [ ] 改森空岛渠道/补奖/cred：已对照 `skland-upstream.mdc`，相关 `test_skland_*` 通过
- [ ] 改塔科夫图鉴/同步/地图标点：已对照 `tarkov-upstream.mdc`（只走 json.tarkov.dev）
- [ ] 改塔科夫联机：非成员 GET 仅为预览；限流与 `docs/security.md`「塔科夫联机」一致
- [ ] 改文件管理：只扫白名单根；敏感文件不可下载；相关 `test_file_manager` 通过
- [ ] 改用户附件：走 `user_files`；OpenAPI `serial`；相关 `test_user_files` 通过
- [ ] 改纯函数/渠道/`force`/弱口令：已按 `testing.mdc` 补测（规则在哪层实现就在哪层测）
- [ ] 改前端请求/报错：走 `*Api` + `apiError`；status 显式传 `force`
- [ ] 改生产相关：核对 `APP_ENV` / 弱口令 / `REDIS_URL`（多实例须共享）/ 邮件日志；发版以绿的 GitHub Release 为准（见 `docs/deploy.md`「发版」）
- [ ] 改 logger：对照 `docs/logging.md`（不刷轮询、不打密钥、任务只打汇总）

## CI

PR/push：`frontend-quality`（lint + vitest + build）· `backend-tests`（pytest）· `backend-migrate-mariadb`（MariaDB 上 alembic）· `openapi-drift`；`dependency-audit` 为 warning、不卡 PR。`main` 仅在质量门绿后发 GitHub Release（static）；门红不改 Release，与没发一样。详见 [`docs/deploy.md`](docs/deploy.md)「发版」。  
提交信息偏好 conventional commits（`feat` / `fix` / `chore` / `docs` / …）。
