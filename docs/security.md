# 安全与运行注意

产品介绍见根 [`README.md`](../README.md)。部署形态与 Redis 多实例约束见 [`deploy.md`](deploy.md)「部署形态」。

- 登录以邮箱为主，也支持 QQ 登录一键开号（回调只带一次性 `ticket`，前端再换会话 Cookie）；无邮箱时可稍后完善
- 默认 JWT 有效期 **24 小时**（`ACCESS_TOKEN_EXPIRE_MINUTES` 或管理端「安全」可调；库内已存配置优先生效）。到期需重新登录，没有 refresh token
- 新签发的 JWT：`sub` 为 **user_id**（数字字符串），另带 `username`。旧票 `sub` 仍是用户名，解码时按是否纯数字区分
- 浏览器会话：登录 / 注册 / QQ 换票 / 安装向导 `Set-Cookie` `zhange_access`（HttpOnly、`SameSite=Lax`、生产 `Secure`、`Path=/`）。前端 **不** 把 JWT 写入 localStorage，axios **不** 塞 `Authorization`。可变方法须带 `X-CSRF-Token`（与可读 Cookie `zhange_csrf` Double Submit）。脚本 / OpenAPI 仍可用 `Authorization: Bearer`（此时免 CSRF）。`POST /api/auth/logout` 清 Cookie。QQ 回调仍只带 ticket
- 生产 CORS：同域部署一般不必放行；若跨源，用 `CORS_ORIGIN_REGEX` 收紧，不要沿用默认 localhost/Tauri 正则
- 管理员高危操作（系统更新、删除用户、保存集成密钥、保存功能开关、保存 SMTP、保存文字识别配置、开启「仅一名管理员」、升管理员或重置他人密码）在 **生产** 须邮箱验证码步进（`X-Step-Up-Code`）；无验证邮箱的管理员须先完善账号。`APP_ENV=development` 跳过该步进，方便本地改配置。生产仍禁止 `ALLOW_EMAIL_CODE_LOG`。发码限流 10/IP、5/账号、5/邮箱 / 10 分钟；校验失败再限 12/账号、12/邮箱 / 10 分钟
- 注销账号：个人中心邮箱验证码；**anonymize** 保留 `users.id`（联机房间历史外键不炸），清空邮箱/口令/显示名，解绑平台与头像（`user_files` 标 `deleted` 并清盘），删酒馆草稿。管理员代删同一套 service，写 `job_runs`
- 平台凭证 Fernet 加密存库。QQ 回调不要把 JWT 放进 URL
- 请求 ID：中间件生成或转发 `X-Request-ID`，写入日志上下文并回写响应头。何时打 logger 见 [`logging.md`](logging.md)
- CSP：默认 `Content-Security-Policy-Report-Only`（`report-uri /api/csp-report`）；`CSP_ENFORCE=true` 后 enforce
- 生产在该环境 `.env` 设置 `APP_ENV=production`（安装脚本**不会**代写）：管理员弱口令默认**拒绝启动**（对库内管理员做常见弱口令探测）。本地 `development` 仅 WARNING；可在管理端「安全设置」覆盖，或遗留 env `REJECT_WEAK_ADMIN_PASSWORD`
- 限流与短时 KV（扫码会话、森空岛 cred 缓存、塔科夫联机 join/大厅）：生产建议设 `REDIS_URL`；本地无 `REDIS_URL` 时进程内降级。多 `app` 实例须共享同一 Redis。默认**不**信任 `X-Forwarded-For`（防伪造绕过）；置于受信反代后可设 `TRUST_X_FORWARDED_FOR=true`
- 本地无 SMTP 时需设 `ALLOW_EMAIL_CODE_LOG=true` 才能用日志收验证码；`APP_ENV=production` 时启动会硬拒绝该开关
- 勿提交 `.env`、`var/`、`data/`、`uploads/`

## 战鸽酒馆

公开页 `/tavern`、`/tavern/:slug`（未登录可看列表、正文、评论；页面走工作台 `AppLayout` 侧栏/顶栏）。写文章须酒馆作者或管理员；发表评论须登录。

- **读权限**：`GET /api/articles` 与分类/标签/**已发布**详情/评论不要求登录 Cookie / Bearer
- **写权限**：发改删文章、上传配图/附件、公式识别、版本恢复：酒馆作者（只动自己的稿）或管理员；删评与作者名单、全量文章列表走管理员；`POST .../comments` 须登录
- **删除**：文章为物理删除（行与评论 / 版本一并去掉），不可恢复
- **限流**（`platform_limiter`；生产靠 `REDIS_URL`）：评论 20/IP/10 分钟、10/账号/10 分钟；发稿 / 改稿 / 配图与附件 40/IP/10 分钟、20/账号/10 分钟；公式识别 10/IP/10 分钟、6/账号/10 分钟
- **正文**：`body_format=html` 入库前经 `nh3` 消毒（去 script / 事件 / `javascript:`），并只保留文章排版 class（对齐 / 缩进 / 调色板 / 高亮 / 公式源）；Markdown 仍由前端 `rehype-sanitize` 渲染。公式只存 LaTeX（`article-math` / `article-math-block`），阅读页再用 KaTeX（`trust: false`）渲染，不入库 KaTeX HTML。识别图只进内存，不落 `uploads/`
- **封面**：只允许 `http(s)` 或站内 `/uploads/...`
- **配图 / 附件**：只挂载 `/uploads/articles`（与头像一样，不暴露整个 upload 根目录）。图片按内容识别 JPG/PNG/WebP/GIF（≤5MB）；附件只收白名单扩展（文档/压缩包等，≤10MB）且校验魔数，拒绝 exe / html / svg。落盘进 `user_files`（流水号 `serial` + 相对路径）；公开 URL 仍是 UUID 路径，**不要**把流水号写进 StaticFiles 路径。管理端「文件管理」只扫盘，不按流水号删文件
- **站内头像**：裁剪为正方形 JPEG 后覆盖写 `avatars/{member_id}.jpg`，登记同一张 `user_files`（`namespace=avatars`）。公开 URL 仍是 `/uploads/avatars/{id}.jpg?v=`，**不要**把流水号写进路径。删头像或注销标 `deleted` 并清盘
- 功能开关 `tavern`（任务配置「战鸽数据」；与站点模型更新同组）；关闭后公开 API 403、侧栏「社区」隐藏

## 塔科夫联机

公开页 `/legal/terms`、`/legal/privacy`（未登录可看；文案在 `frontend/src/lib/legalDocs.ts`）。邮箱注册须勾选同意；登录 / QQ 登录旁注明即表示同意。页脚备案号由运营者配置（管理端「安全设置」或 `ICP_BEIAN_NO`），留空不展示。

- **读权限**：未入座 `GET /api/guides/tarkov/raid-rooms/{id}` 只回预览：标题、地图、`game_mode`、是否上大厅、人数、`max_members`、是否要密码、`created_at`、`is_host`（`is_member=false`）。不含人员名单、房主 user_id、认领、标点、钥匙、目标完成、进度重叠。公开大厅列表仍展示公开房的在座昵称。房间 WebSocket 须已入座
- **写权限**：认领 / 标点 / 设密等须在座；密码只在 **join** 时校验
- **限流**（`platform_limiter`；生产靠 `REDIS_URL`）：创建 20/IP/10 分钟、10/账号/10 分钟；加入（含密码错误）10/IP+房间/10 分钟、10/账号+房间/10 分钟；大厅列表 40/IP/分钟、40/账号/分钟
- **大厅查询**：只加载当前顶栏模式、`listed` 且无密码、仍有人在座的房；过期座位按 `last_seen` 定向回收，不把全部房间扫进内存
- **日志**：客户端本机解析；库表 `tarkov_user_raid_logs` 只存摘要。截图坐标只广播数字，不传图片；最近一次坐标留在进程内存，供同房间晚加入的入座成员（含同一账号的其他设备）从 WS snapshot 拿到，不落库

## 文字识别

引擎、权重与场景选择是站点能力（`system_configs.ocr`，管理端「站点设置 → 文字识别」）。上区一族一张卡（熊猫 OCR / EasyOCR），下区业务勾选族并设多端校验。熊猫档位从本机 RapidOCR `default_models.yaml`（onnxruntime）摊开。生产保存配置须步进验证码；开发环境跳过。**没有**对外 `POST /api/ocr/recognize`；业务只走内部 Python 接口。权重在 `var/data/rapidocr` 与 `var/data/easyocr`，由本页「检查更新」或任务配置「文字识别模型」（`ocr_model_sync`）按当前 Paddle 档位预拉；识别时不现场下载。未就绪返回 503。公式识别（TexTeller）仍独立，走任务配置「公式识别模型」，不并进这套引擎。

## 文件管理

管理端「运行维护 → 文件管理」只给管理员：统计本站运行时 / 模型 / 缓存 / 依赖占用，并浏览白名单根（安装根、其下的 `var/` / venv / `node_modules`、备份目录、家目录下 Hugging Face / Torch 缓存等）。**禁止**把查询参数当成任意绝对路径；越出白名单根返回 400。`.secret_key`、`.env`（不含 `.env.example`）、`.git`、密钥类后缀、`var/mariadb/data` 与 `var/mariadb/provision.json`、以及站点备份 `zhange-*.tar.gz` / `zhange.sql` 列出时置灰：敏感目录不可进入，文件不可下载。塔科夫图鉴 dump 在数据库，Minecraft 服文件在 Pelican，都不走这套本机浏览。不提供删除。用户上传元数据在 `user_files`（按流水号查路径；酒馆 UUID、头像覆盖 `member_id.jpg`），不要和管理端盘点混成一个「文件服务」。

## 塔科夫钥匙截图识别

钥匙管理「截图识别」把用户粘贴的钥匙箱截图 `POST` 到本站，按 360–640（最佳约 540）正方形切块，按「文字识别」里为场景 `tarkov_keys` 勾选的引擎读格子 **shortName**（默认熊猫 OCR + EasyOCR）。每族另走反色补召回；该业务默认开启多端校验，模糊匹配须两个不同模型族同时读到，才放宽阈值。切块与闭集匹配仍在塔科夫业务里。响应只带回文本框坐标供覆盖层，原图与切块只进内存，不落 `uploads/`、不入库。确认后才 `merge` 到 `tarkov_user_key_owns`。限流：8/IP/10 分钟、6/账号/10 分钟；进程内同时只跑 1 路识别，客户端断开后工作线程在下一刀切块前退出。

## 塔科夫工作台出图

工作台中间用 dump 枪图做底板，在图上点槽位换配件。第三方出图接口默认关闭（`TARKOV_WORKBENCH_IMAGE_GEN=false`）。若手动打开，限流仍为出图 `POST /api/guides/tarkov/workbench/build-image` 40/IP/10 分钟、20/账号/10 分钟；返回的 `image_url` 只接受 `image-gen.tarkov-changes.com`。

## 塔科夫工作台社区方案

选枪后可浏览 EFTForge **公开**社区方案（`GET /builds/public?gun_id=`）。只读列表，投影成本站 dump 可装的 `pairs`；不落库（短时 KV 缓存原始 JSON）、不代投票/评论、不热链对方卡图。对方仓库为 MIT，社区用户内容按公开列表展示并署名来源。关闭：`TARKOV_WORKBENCH_COMMUNITY=false`。限流：`GET /api/guides/tarkov/workbench/community-builds` 30/IP/10 分钟、20/账号/10 分钟。

对外宣传前的环境核对见 [`deploy.md`](deploy.md)「公开运营检查」。

平台数据约定（养成盒 / 旁路 raw、签到展示始终 force 回源）见 [`.cursor/rules/platform-raw-cache.mdc`](../.cursor/rules/platform-raw-cache.mdc)。森空岛官服/B服与补奖见 [`.cursor/rules/skland-upstream.mdc`](../.cursor/rules/skland-upstream.mdc)。
