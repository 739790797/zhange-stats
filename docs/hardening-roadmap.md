# 战鸽数据 · 公开站点规范对齐（分期落地）

> 状态：**已落地**（2026-09-08）  
> 对照：OWASP 基线、WCAG 2.2 可操作项、国内备案站常见运维、个人信息保护的产品侧期待。  
> 不是 ISO/等保全文，也不把本站改成多活 K8s。单副本 LXC 约束见 [`deploy.md`](deploy.md)「部署形态」。

人读入口：[`docs/README.md`](README.md)。本页为已落地验收清单；不要另写第二份「规范」。

## 原则

- **一期一件可合并的主题**，避免「安全大 PR」。
- 先运维与会话，再无障碍与隐私入口，最后 CSP / Cookie（依赖前面收敛）。
- **禁止**半套会话改造：不要去掉 CSRF / 登出清 Cookie / 生产 CORS 收紧，却只把 JWT 改成可读 Cookie 或继续 persist JWT（见 [`security.md`](security.md)）。
- 已有约定继续有效：限流、弱口令、Fernet、生产关 Swagger、酒馆消毒、塔科夫非成员预览。本路线不推翻它们。

## 总览

| 期 | 主题 | 体量 | 依赖 | 状态 |
|----|------|------|------|------|
| 0 | 页面壳：动效、标题、换页回顶、antd `App`、路由错误边界 | 已做 | — | **已落地**（2026-09） |
| 1 | 反代安全头、备份、去掉 Google 字体 | S～M | — | **已落地**（2026-09-08） |
| 2 | 收敛 401 整站登出 | S | — | **已落地**（2026-09-08） |
| 3 | 无障碍：跳到正文、`main`、换页焦点 | S | 0（换页回顶） | **已落地**（2026-09-08） |
| 4 | 删号入口与隐私条款对齐 | M | 邮件可用 | **已落地**（2026-09-08） |
| 5 | 管理员高危操作二次确认（邮箱验证码） | M | SMTP | **已落地**（2026-09-08） |
| 6 | 请求 ID + 前端错误上报（脱敏） | M | 1 的日志习惯 | **已落地**（2026-09-08） |
| 7 | CSP：先 Report-Only 再收紧 | L | 1 字体自托管 | **已落地**（Report-Only；`CSP_ENFORCE` 默认关） |
| 8 | JWT → httpOnly Cookie + CSRF | L | 7 稳定、同域部署 | **已落地**（2026-09-08） |
| 附 | 酒馆检索策略、依赖审计（非门禁） | S | 产品二选一 | **已落地**（A：全站 noindex；CI audit warning） |

**明确不做（本路线结束也不做）：** 主应用暗色、i18n、PWA、水平扩展 / Redis pub/sub 联机（另立项）、Lighthouse/axe 进 CI 门禁（3 期完成前）、完整 TOTP/WebAuthn（5 期邮箱码足够）。

---

## 0 期（已落地）

页面切换淡入、`prefers-reduced-motion`、文档标题、`AppLayout`/塔科夫换页回顶、antd `App`、`RouteErrorBoundary`。约定见 [`.cursor/rules/frontend-ui.mdc`](../.cursor/rules/frontend-ui.mdc)。

本路线不再重复这些工作。

---

## 1 期 · 反代安全头、备份、字体

**目标：** 备案站最常见的三件运维缺口一次补齐：响应头、能恢复的备份、不再把访客 IP 送给 Google Fonts。

### 1.1 安全头（反代）

改 [`deploy.md`](deploy.md) nginx 示例，并在生产反代落地。应用进程也会发同一套头与 `X-Request-ID`（无反代的裸 uvicorn 仍可用）；生产以反代为准，重复头可接受。

在 `location /`（及需要的 `location /assets/`）增加，注意 nginx 的 `add_header` 在有 `location` 时不会继承，**每个会返回用户响应的 location 都要写**：

```nginx
add_header X-Content-Type-Options "nosniff" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header X-Frame-Options "DENY" always;
add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;
# 仅 HTTPS 站点：
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
```

**不要**在 1 期上 CSP（见 7 期）。`X-Frame-Options` 与日后 `frame-ancestors 'none'` 只留一套即可。

验收：

- [x] 生产响应（HTML 与 `/health`）能看到上列头
- [x] WebSocket 升级（联机房间）仍可用
- [x] `docs/deploy.md` 示例与线上一致
- [x] 「公开运营检查」表增加「安全头 / HSTS」一行

### 1.2 备份与恢复

单机 LXC，备份对象：

| 对象 | 路径 / 命令 |
|------|----------------|
| MySQL | `mysqldump`（含例行 `--single-transaction`）；库名来自 `DATABASE_URL` |
| 运行时 | `var/data/`（含 `.secret_key`、日志、TexTeller 权重）、`var/uploads/` |
| 配置 | 安装根 `.env`（**不要**进 Git；备份目录权限仅 root/zhange） |

建议：

- 脚本放 `scripts/backup.sh`（读 `.env` 的 `DATABASE_URL`，输出到例如 `/var/backups/zhange/` 带日期的 tar）
- `scripts/restore.sh` 写明：停服务 → 导库 → 解压 `var/` → 启动；**不**在文档里只写 dump 不写 restore
- systemd timer 或 cron：每日一次，保留 7～14 天；备份盘与数据盘分离更佳
- 演练：在非生产或停机窗口做一次 restore 到临时库，确认能登录

验收：

- [x] `docs/deploy.md` 有备份/恢复步骤，且「公开运营检查」含「最近一次成功备份日期」
- [x] 至少一次恢复演练有记录（日期即可，不必把备份文件提交进仓库）

### 1.3 字体不再走 Google

现状：[`frontend/index.html`](../frontend/index.html) 全站拉 `fonts.googleapis.com`（IBM Plex / Noto SC / Rajdhani）。主应用主题已是系统黑体（`antdAppTheme`）；塔科夫壳用 Plex + Rajdhani，CJK 已在 `tarkovFonts.css` 用本机字体补汉字。

落地：

1. 从 `index.html` **删除** Google `preconnect` 与 stylesheet（主应用零损失）。
2. 塔科夫：二选一（优先 A）  
   - **A.** `frontend/src/assets/fonts/` 自托管 **拉丁子集** woff2（IBM Plex Sans/Mono、Rajdhani），仅 `TarkovGuideShell` 引入；遵守 SIL OFL，在致谢/README 保留来源。  
   - **B.** 不再加载 Plex/Rajdhani 文件，CSS 改为 `Arial Narrow` / 系统等宽；观感会变，但零外链。
3. 构建后 Network 面板在攻略页也不应再请求 `fonts.gstatic.com`。

验收：

- [x] 生产首页与塔科夫首页无 `fonts.googleapis.com` / `fonts.gstatic.com`
- [x] 主应用字形仍为黑体；塔科夫汉字不出现 `???`（`tarkovFonts.css` 的 CJK `@font-face` 保留）

---

## 2 期 · 收敛 401 登出

**目标：** 避免一张过期票或某个接口 401 把整次会话踢掉。

现状：[`frontend/src/api/http.ts`](../frontend/src/api/http.ts) 非 `/auth/login` 的 401 立刻 `logout()`。

规则（实现时写成纯函数并单测，见 [`testing.mdc`](../.cursor/rules/testing.mdc)）：

1. **无 token 的请求** 401：不登出（访客打了需登录接口）。
2. **明确未登录探针**（如 `GET /api/auth/me`）401：登出。
3. **带 token 的业务 401**：登出，但 **同一时刻只执行一次**（锁 / 标志位），避免并发 10 个 401 清 10 次并乱跳登录页。
4. **不要**对 403 登出（没权限 ≠ 没登录）。
5. 登录页自己的失败 401 仍只展示错误（已排除 login URL）。

可选增强（仍属 2 期，可同一 PR）：过期前不自动续期（没有 refresh token）；文档写清「24h 到期需重新登录」。Refresh token **不要**在 2 期做（会变成 8 期 Cookie 方案的一半）。

验收：

- [x] 纯函数测：无 token / login URL / 403 / 并发 401
- [x] 手动：未登录打开需登录 API 不把已登录的另一标签误踢（同源 Cookie 本来就共享）
- [x] 访客酒馆阅读不因某个 401 被拉去登录页（除非点了写操作）

---

## 3 期 · 无障碍（WCAG 可操作项）

**目标：** 键盘与读屏能进主内容，换页后焦点不丢在侧栏。不做 axe 门禁。

改 [`AppLayout.tsx`](../frontend/src/components/AppLayout.tsx)（塔科夫壳同步）：

1. 视口顶部「跳到正文」链接（默认视觉隐藏，`:focus` 可见），`href="#app-main"`。
2. 主栏滚动容器加 `id="app-main"`、`tabIndex={-1}`、语义 `main`（antd `Content` 用 `component="main"` 或外包 `<main>`）。侧栏 `nav` + `aria-label="站点"`（若尚未）。
3. pathname 变化时：已有 `scrollTo(0,0)`，再 `mainRef.current?.focus({ preventScroll: true })`。
4. 0 期已尊重 `prefers-reduced-motion`，3 期只确认跳转链接也无额外动效。

塔科夫：`.body` 作为该壳的 `main`，跳转目标不要和主站 `id` 冲突（例如 `#tarkov-main`），跳到正文链接在攻略顶栏前。

验收：

- [x] 仅键盘：Tab 先到「跳到正文」，回车后下一个 Tab 在主栏，不经过整列菜单
- [x] 换页后焦点在 `main`（屏幕阅读器会报主内容）
- [x] 移动端顶栏菜单仍可打开；塔科夫搜索 `/` 快捷键仍可用

---

## 4 期 · 删号与隐私对齐

**目标：** 隐私说明里「删除账号请联系运营者」变成**站内可完成或可工单化**的路径，避免条款空口。

产品默认（可在开工前改一句，但必须写进本段）：

- 用户在个人中心申请删除：邮箱验证码（复用现有发码限流）→ 后端**硬删除或 anonymize** 必须二选一并写进 `docs/database.md`。
- **建议 anonymize：** 用户行保留 id（联机房间历史外键不炸），邮箱/QQ/口令清空，显示名改为「已注销用户」，解绑全部平台凭证（Fernet 密文删除），头像文件删。酒馆文章：保留已发布稿、作者显示为已注销；草稿物理删。
- 管理员代删走用户管理页，同一套 service，写 `job_runs` 或现有审计习惯（不要新造一套日志平台）。

条款：[`legalDocs.ts`](../frontend/src/lib/legalDocs.ts) 隐私段改为「可在个人中心申请注销；处理时限（例如 15 日）」。`updated` 日期改当天。

验收：

- [x] 有 API + 个人中心入口；限流与发码策略与注册同级
- [x] 注销后无法用原邮箱登录；平台绑定已解
- [x] 隐私页与实现一致；`docs/database.md` 写清用户行命运
- [x] 测：发码限流、错误码、二次提交幂等

---

## 5 期 · 管理员高危二次确认

**目标：** 系统更新、删除用户、保存集成密钥，不能只靠已登录的管理员 JWT。

做法：**邮箱验证码**（不引入 TOTP 应用）。无邮箱的管理员（仅 QQ）必须先完善邮箱（已有完善账号流），否则这些按钮禁用并提示。

建议覆盖：

- `POST` 系统更新 / 应用更新
- 删除用户
- 保存「集成密钥」（Pelican / 出图等）
- （可选）关闭 `tavern` 等全局功能开关

实现：`POST /api/auth/step-up/send` + 写操作带 `code`；验证码短 TTL（5～15 分钟），`auth_limiter` 限额与绑邮箱同级。前端 Modal：先发码再提交原表单。

验收：

- [x] 无码或错码不能更新/删用户/改集成密钥
- [x] 生产仍禁止 `ALLOW_EMAIL_CODE_LOG`
- [x] 普通用户界面无这些入口（已有 `AdminRoute`）

---

## 6 期 · 请求 ID 与前端错误上报

**目标：** 排障能把「某次点击」对上 journal 一行；白屏不只存在用户控制台。

### 6.1 请求 ID

- 中间件：若无 `X-Request-ID` 则生成 UUIDv4，写入 `log_context`，响应头带回。
- axios：把响应头存到本次错误对象，`RouteErrorBoundary` / `apiError` 可选展示「编号 xxxxxxxx」（不要把 ID 当密钥）。

验收：一次失败的 API，浏览器响应头与服务器日志同一 ID。

### 6.2 前端渲染错误

- `RouteErrorBoundary` 在 `componentDidCatch` 后 `POST /api/client-errors`（需登录，限流如 10/IP/10 分钟）。
- 体：`message`、`componentStack` 截断、`pathname`、`request_id`（若有）、`app_version`。**不要**上报输入框内容、token、DOM 全文。
- 存储：现有运行时日志缓冲或轮转文件即可，管理端「平台日志」能看到；不要新上一套 Sentry 云（可在注释里留 hook，禁止默认把生产堆栈送到第三方）。

验收：本地故意 throw，管理端能看到一条；无 JWT 时接口 401 且不写敏感体。

---

## 7 期 · CSP

**依赖：** 1.3 完成（无 Google Fonts）。antd 大量内联 style，**第一阶段必须 Report-Only**。

1. 反代加 `Content-Security-Policy-Report-Only`，`report-uri` 指到 6.2 同类限流接口或仅文件日志。
2. 初值建议（按实际上报收紧，不要一次 `default-src 'self'` 上生产 enforce）：

```
default-src 'self';
script-src 'self' https://static.geetest.com;
style-src 'self' 'unsafe-inline';
img-src 'self' data: blob: https:;
connect-src 'self' wss: https:;
font-src 'self';
frame-src 'self' https://static.geetest.com https://gcaptcha4.geetest.com;
worker-src 'self' blob:;
frame-ancestors 'none';
base-uri 'self';
form-action 'self';
```

`img-src` 需覆盖 Steam/森空岛/塔科夫 CDN、文章配图；`connect-src` 覆盖本 API 与 json.tarkov.dev（若浏览器直连；以实际为准）。地图瓦片、blob 预览都要在 Report-Only 里跑一周再 enforce。

3. 与 1.1 的 `X-Frame-Options` 并存可以；enforce 后可只留 CSP `frame-ancestors`。

验收：

- [x] Report-Only 至少观察一轮真实流量，无误杀联机 WS / 地图 / KaTeX
- [x] enforce 后文档与反代示例更新；错误报告可查

---

## 8 期 · httpOnly Cookie + CSRF

**依赖：** 同域部署（当前 SPA 与 API 同 origin 经反代）；7 期 CSP 不再靠「任意 inline script」。

按 [`security.md`](security.md) 已写条件整包做，禁止半套：

1. 登录 / 注册 / QQ 换票：`Set-Cookie`（`Secure`、`SameSite=Lax` 或 `Strict`、`HttpOnly`、`Path=/`）。
2. 前端去掉 zustand 对 JWT 的 persist；axios **不再**塞 `Authorization`（依赖 Cookie）。
3. CSRF：同站 Lax 对「简单 GET」够用；所有 **状态改变** 的 POST/PATCH/DELETE 要求自定义头（如 `X-CSRF-Token`）或 Double Submit Cookie。从后端发 CSRF cookie（可读）+ 头校验。
4. 登出：清 Cookie。
5. 文档：CORS 收紧为生产站 origin（今日正则含 localhost/Tauri，生产应用 `CORS_ORIGIN_REGEX` 覆盖）。

验收：

- [x] DevTools 看不到可被 JS 读取的 access token
- [x] 跨站表单 POST 不能改状态（CSRF 测）
- [x] QQ 回调仍只带 ticket，不把 JWT 放 query
- [x] 未完成前 **禁止** 只改前端不改后端

---

## 附件 A · 酒馆检索策略

开工前运营选一个，写进本段并改代码。**已选 A**（2026-09-08）：全站 `noindex,nofollow`，`GET /robots.txt` 为 `Disallow: /`。

| 选项 | 做法 |
|------|------|
| **A. 不希望被搜到**（默认建议） | `index.html` 与酒馆公开页 `meta name="robots" content="noindex,nofollow"`；`/robots.txt` Disallow 按需 |
| **B. 希望文章被索引** | 仅 `/tavern/:slug` 输出 `description`（摘要消毒后截断）、`og:title`；列表页仍 noindex；不要给后台/签到页做 SEO |

验收：选 A 则搜索预览抓不到后台路由；选 B 则文章源码有 description，登录页仍 noindex。

---

## 附件 B · 依赖审计（非门禁）

- CI 增加 **可失败为 warning** 的 `npm audit --omit=dev` 与 `pip-audit`（或 Dependabot 告警），**不要**卡 PR。
- 高危且有修的依赖在常规迭代里升，不单开「审计大月」。

---

## 落地后改哪些文档

| 期 | 必须同步 |
|----|----------|
| 1 | `deploy.md` 反代示例、公开运营检查、备份/恢复 |
| 2 | 可选：`frontend-api-errors.mdc` 一句「401 登出规则」 |
| 3 | `frontend-ui.mdc` 跳转正文 / `main` |
| 4 | `legalDocs.ts`、`database.md`、`security.md` 一句删号 |
| 5 | `security.md` 管理员步进 |
| 6 | `deploy.md` 或 `security.md` 请求 ID |
| 7 | `deploy.md` CSP |
| 8 | `security.md` Cookie/CSRF（改写现 JWT 条）；`AGENTS.md` 禁止清单去掉「未做 CSRF 前…」并改为新禁令 |
| 附 A | `frontend/index.html` 或文章页；本路线状态表 |

全部 1～8 完成后：把本文状态改为 **已落地（日期）**，总览表打勾。不要另写第二份「规范」。

**已于 2026-09-08 全部落地。** enforce CSP 仍默认关：观察 `zhange.csp` 无误杀后再设 `CSP_ENFORCE=true`。恢复演练日期由运营记在运维笔记。

## 建议开工顺序

同一周不要并行 7 和 8。默认顺序即表序，已按该顺序落地。附件 A 选不索引；附件 B 为 CI warning、不卡 PR。
