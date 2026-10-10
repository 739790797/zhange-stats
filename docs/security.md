# 安全与运行注意

产品介绍见根 [`README.md`](../README.md)。部署形态与 Redis 多实例约束见 [`deploy.md`](deploy.md)「部署形态」。

- 登录以邮箱为主，也支持 QQ 登录一键开号（回调只带一次性 `ticket`，前端再换会话 Cookie）；无邮箱时可稍后完善。ticket 2 分钟内有效，换票用带条件的 `DELETE ... WHERE code=? AND expires_at>=now` 抢占，同一张并发来换只有删到那一行的请求拿到会话
- 默认 JWT 有效期 **24 小时**（管理端「安全」可调，写入 `config/auth.json`），最长 **30 天**：配置写得更长也按 30 天签发。到期需重新登录，没有 refresh token
- 签发的 JWT：`sub` 为 **user_id**（数字字符串），另带 `username` 与 `ver`。签名密钥是 `SECRET_KEY` 的 HKDF 子密钥（`key_derivation.PURPOSE_JWT`）。升级前直接用 `SECRET_KEY` 签、不带 `ver` 的令牌只在剩余有效期不超过 30 天时还认，最迟 30 天后全部失效
- 会话撤销：`ver` 须等于 `users.token_version`，否则按未登录处理。改密、找回重置、管理员改口令、降为普通用户（含「只留一名管理员」自动降级）、注销账号、`POST /api/auth/logout-all`（退出所有设备）都会把 `token_version` 加 1，该账号已签发的令牌全部失效。自己改密时当前浏览器随响应换发新 Cookie，不掉线
- 浏览器会话：登录 / 注册 / QQ 换票 / 关联已有账号 / 安装向导 `Set-Cookie` `zhange_access`（HttpOnly、`SameSite=Lax`、`Path=/`）。这些接口与改密、改用户名换发的令牌都只进 Cookie，响应体不回 JWT（只有 `ok` / `message` 或用户信息）。`Secure`：请求是 HTTPS（含反代首段 `X-Forwarded-Proto: https`）一律带；`APP_ENV=production` 下 HTTP 也带，只有安装向导建管理员那次响应例外（否则纯 HTTP 内网装完即掉线）。前端 **不** 把 JWT 写入 localStorage，axios **不** 塞 `Authorization`。可变方法须带 `X-CSRF-Token`（与可读 Cookie `zhange_csrf` Double Submit）；可选登录的公开接口带着会话 Cookie 发可变请求同样校验，对不上就 403，不会悄悄降成访客。脚本 / OpenAPI 仍可用 `Authorization: Bearer`（此时免 CSRF）。`POST /api/auth/logout` 清 Cookie。QQ 回调仍只带 ticket
- OAuth 回跳：QQ 登录、QQ 绑定、Steam 绑定的回跳前端只在白名单里选：`PUBLIC_FRONTEND_URL`、后端同源地址、`CORS_ORIGINS`，以及当前生效的 CORS 正则（非生产默认放行本机 Vite 任意端口，生产只认显式 `CORS_ORIGIN_REGEX`）。`Origin` / `Referer` 只用来在白名单内挑一项；回调时按本次请求重算，state 里记的地址不在白名单就退回默认站点
- QQ 授权绑定浏览器：发起时写 HttpOnly Cookie `zhange_qq_nonce`（`Path=/api/auth/qq`、`SameSite=Lax`、15 分钟），state 只存其 SHA-256，并用 HKDF 子密钥 `PURPOSE_OAUTH_STATE` 签名。回调对不上（换了浏览器、清了 Cookie、授权链接被转发）就带 `reason=browser_mismatch` 跳回，成败都清掉该 Cookie。QQ 回调地址须与用户浏览的站点同主机才带得上这个 Cookie（同域部署天然满足；开发时别混用 `localhost` 与 `127.0.0.1`）
- Steam 绑定（OpenID 2.0）：发起时同样写 HttpOnly Cookie `zhange_steam_nonce`（`Path=/api/profile/steam/openid`、15 分钟），state 只存其 SHA-256 并带一次性 `jti`，用同一把 `PURPOSE_OAUTH_STATE` 子密钥签名（`purpose` 不同，QQ 的 state 在这里不认）。回调依次核对：state 签名与有效期 → 本浏览器 nonce → state 没用过（短时 KV 登记 `jti`，同一 state 只认一次）→ `openid.mode=id_res`、`openid.ns` 与 `openid.op_endpoint` 是 Steam 官方 → `openid.return_to` 与本次回调地址（含 state）逐字相同 → `openid.signed` 至少覆盖 `op_endpoint,claimed_id,identity,return_to,response_nonce,assoc_handle` → `claimed_id` 等于 `identity` 且是 `steamcommunity.com/openid/id/<17 位>` → `response_nonce` 的时间戳在前后 5 分钟内且没用过（短时 KV 单次登记，先占再去 Steam 校验）→ 最后把断言原样交给 Steam `check_authentication`（POST，403/405 改 GET），只认应答里的 `is_valid:true`。别的「用 Steam 登录」站点拿到的断言、或配上自己 state 的断言，在这里换不成绑定
- OAuth 回跳参数：QQ 登录 `qq_login=ok|error`、QQ 绑定 `qq_bind=ok|error`、Steam 绑定 `steam_bind=ok|error`；失败另带固定码 `reason`，前端按码出文案。URL 里不放 QQ / Steam 返回或异常的任何原文，原文只进服务端日志（同类故障 `log_until_change` 去重，异常 `logger.exception`）。QQ 登录成功另带一次性 `ticket`，账号没邮箱时再带 `need_complete=1`。码表：

  | `reason` | 含义 | 出现在 |
  |---|---|---|
  | `cancelled` | 用户在 QQ / Steam 页取消授权 | 全部 |
  | `state_invalid` | state 缺失、签名不对、过期，或（Steam）已用过 | 全部 |
  | `browser_mismatch` | 回调不在发起的那个浏览器（nonce Cookie 对不上） | 全部 |
  | `upstream_error` | QQ / Steam 接口报错或连不上 | 全部 |
  | `server_error` | 服务端异常 | 全部 |
  | `missing_code` | QQ 回调没带 `code` | QQ 登录、QQ 绑定 |
  | `account_create_failed` | QQ 一键开号生成不了唯一用户名 | QQ 登录 |
  | `user_not_found` / `member_not_found` | 发起绑定的账号 / 目标成员已不存在 | QQ 绑定、Steam 绑定 |
  | `forbidden` | 非管理员给别的成员绑定 | QQ 绑定、Steam 绑定 |
  | `already_bound` | 该 QQ / Steam 已绑在别的成员上 | QQ 绑定、Steam 绑定 |
  | `bind_failed` | 其他绑定校验失败 | QQ 绑定、Steam 绑定 |
  | `verify_failed` | Steam 断言不合格（`return_to`、签名字段、`claimed_id`、`is_valid`） | Steam 绑定 |
  | `expired` / `replayed` | Steam `response_nonce` 超出前后 5 分钟 / 已用过 | Steam 绑定 |
  | `steam_private` / `steam_not_found` | Steam 资料未公开 / 解析不到该账号 | Steam 绑定 |
  | `feature_disabled` | Steam 功能已关闭 | Steam 绑定 |
- 口令：直接用 `bcrypt` 库（不经 passlib），只取前 72 字节，与旧 passlib 哈希互认。注册 / 改密 / 重置 / 管理员设口令都按原样存（不去首尾空白），不能含空字符。旧版改密 / 重置会去掉首尾空白再存，所以登录与「当前密码」先按原样比，不中再试去空白后的值
- 设口令时（注册、改密、找回重置、绑定邮箱顺带设的口令、管理员建号 / 改口令、安装向导）超过 72 字节（UTF-8，字母数字符号各 1 字节、汉字约 3 字节）直接 400「密码过长：最多 72 字节…」，不静默截断。接口层另有长度上限：口令输入 256 字符、登录账号 128 字符；注册 / 找回 / 绑定邮箱的口令校验排在核销验证码之前，口令不合格不浪费验证码。`ALLOW_ENV_ADMIN_SEED` 播种时 `ADMIN_PASSWORD` 先去首尾空白再校验、再存，`.env` 里常带的尾随换行不会变成登录框打不出来的口令
- 显示名不收 `<` `>`（安装向导、个人资料、管理员建号 / 改资料回 400「显示名不能包含 < 或 >」）；QQ 昵称写库前去掉这两个字符。显示名会进 Leaflet tooltip 等按 innerHTML 渲染的地方，前端转义之外后端再挡一层。存量显示名不自动改
- 生产 CORS：同域部署一般不必放行；若跨源，用 `CORS_ORIGIN_REGEX` 收紧，不要沿用默认 localhost/Tauri 正则

## 战鸽助手

Windows 桌面端 zhange-app 用系统 WebView 打开**本站同源地址**。站点响应带 `X-Frame-Options: DENY` 与 CSP `frame-ancestors 'none'`，不能用 iframe 嵌进来。开发环境 CORS 正则里的 `https://tauri.localhost` 只给本机联调；生产不要把壳源跨站打 API 当成登录方案（Cookie 为 `SameSite=Lax`，前端请求相对路径 `/api`，生产默认不放行该正则）。会话仍是 HttpOnly Cookie + CSRF。QQ / Steam 回跳必须落在站点地址。

助手自带侧栏时，站点在嵌入标记下不画 `AppLayout` 的「战鸽数据」侧栏；浏览器直接打开不变。塔科夫页内栏目顶栏仍由页面负责。个人中心要嵌成子页时，嵌入之外再标 `pane: "body"`（或 `?pane=body`）：`/guides/tarkov/me?tab=collection&embed=assistant&pane=body` 只画该 tab 主体（收集格子、任务列表等），不画顶栏、面包屑和 tab 条。综合查询用 `?pane=search`：`/guides/tarkov?embed=assistant&pane=search` 只画搜索框，不画顶栏、目录和页脚；搜到结果后仍列出结果。`pane=search` 只认当前地址。没有嵌入标记时 `pane` 不生效。

截图目录与游戏日志的读盘交给助手：列目录、读日志文本、读最新截图、按页面「多于 N 张删旧图」删除、目录一变就通知页面。文件名里的坐标、日志解析、任务回放留在站点前端。战局只提交现有摘要接口，房间定位只广播数字。钥匙箱与局前任务的截图识别仍走现有 `recognize`，图只进服务器内存，确认后只存 id。

助手在页面脚本前设置 `window.zhangeAssistant`，或让地址带 `?embed=assistant`（站点记入 `sessionStorage`，站内跳转仍算嵌入）。联机房间 WebSocket 鉴权在嵌入时带 `client=desktop`，浏览器为 `web`。`embed: true` 时不画网页侧栏。`pane: "body"` 或 `?pane=body` 记入同一会话，只在已嵌入时让个人中心当前 tab 去掉外壳。`?pane=search` 不记入会话，只让当前首页去掉外壳，只留搜索框。`tarkovFiles.screenshots` / `logs` 提供 `path`、`list(relativeDir?)`、截图 `readBytes`、日志 `readText`、截图 `remove`、`watch`。相对路径用 `/`，`list` 只回当前层名字。`rebindScreenshots` / `rebindLogs` 可选，供页面「更换」。`pickImage()` 返回 `{ name, type, bytes }` 时，钥匙箱与局前任务识别弹窗多一个「从助手选择截图」，识别仍走现有接口。

助手首页是 `/app`。打开时请求 `/auth/me`：401 去登录页；没有状态码或其它 4xx/5xx 留在页上重试，不当成未登录。页内卡片仍是演示。

改这些行为时对照 [`.cursor/rules/zhange-assistant.mdc`](../.cursor/rules/zhange-assistant.mdc)。

- 管理员登录即可改配置、系统更新、删用户；**不再**要求邮箱步进验证码。管理员会话被盗即等于能改配置。继续靠 HttpOnly Cookie、CSRF、生产 `Secure`、短 JWT。注册 / 绑定邮箱 / 找回 / 注销账号的**用户侧**验证码保留。生产仍禁止 `ALLOW_EMAIL_CODE_LOG`。用户侧验证码是 6 位数字，有效期取「邮箱设置」但最长 30 分钟（设置接口只收 1–30，`config/email.json` 里写得更大也按 30 分钟算，邮件里写的就是封顶后的值）；同一码输错 5 次即作废，须重新获取（重发会清零计数，`register_challenges.attempts`）。发码与校验的次数见下方「账号相关限流」
- 邮箱是否注册不外泄：注册发码 / 重发 / 找回发码 / 绑定邮箱发码先判断邮件发不发得出去（发不出去对任何地址都同样 503），再查库。已注册邮箱申请注册、没有可找回账号的邮箱申请找回、已被别的账号占用的邮箱申请绑定，照样记一条验证码，只是收到的是不带验证码的提醒信；接口响应（状态码、文案、`delivery`）与正常邮箱逐字相同，`delivery` 不再出现 `skipped`。注册 / 验证邮箱 / 重置 / 绑定邮箱先核销验证码再看账号：码不对一律「验证码错误」，「邮箱已被注册」「重置失败，请检查邮箱与验证码」「该邮箱已被其他账号使用」只有拿到码的人才看得到；验证邮箱遇到没有账号的邮箱回通用错误，并把码留给注册用。登录与关联已有账号在账号不存在时也对固定的哑哈希跑一次 bcrypt，耗时与输错口令一样
- 账号安全提醒：QQ 临时号合并进已有账号、或在个人中心绑定 QQ 成功后，给该账号已验证的邮箱发一封提醒（放 `BackgroundTasks` 尽力而为，不阻塞、不改变接口结果；站点没配邮件就跳过，发送异常只记 WARNING，不带收件人与异常原文）。关联已有账号前先拒掉带着任何平台绑定（含米游社）或 Steam 的临时号，免得合并时把这些绑定悄悄删掉
- 成员资料：`GET /api/members/{id}/profile` 登录即可看，但只有本人和管理员拿全量。其他登录用户只拿显示名 / 昵称、头像、加入时间、各平台与 QQ 是否已绑、Steam 昵称与头像；登录名、邮箱、`user_id`、SteamID、QQ 昵称与头像、各平台手机号掩码与自动签到开关一律为空
- 注销账号：个人中心邮箱验证码；**anonymize** 保留 `users.id`（联机房间历史外键不炸），清空邮箱/口令/显示名，解绑平台与头像（`user_files` 标 `deleted` 并清盘），删酒馆草稿，删掉该账号在全部 `tarkov_user_*` 表里的行（任务进度、钥匙、收集、资料、地图筛选、藏身处、战局摘要、raid-prep；新增此类表须加进 `PERSONAL_TARKOV_MODELS`，有测试兜底）。联机房间的成员 / 标点 / 钥匙行留作房间历史，但入座时抄下的显示名（`tarkov_raid_room_members.display_name`、`tarkov_raid_rooms.host_display_name`）换成「已注销用户」。同时 `token_version` 加 1，所有设备立即登出。注销或降级管理员时先锁住管理员行、改完再复核，并发操作也至少留一名管理员。管理员代删同一套 service，写 `job_runs`
- 平台凭证 Fernet 加密存库。QQ 回调不要把 JWT 放进 URL
- 凭证密钥：新密文用 `SECRET_KEY` 的 HKDF 子密钥（`key_derivation.PURPOSE_FERNET`），旧版 `sha256(SECRET_KEY)` 密文仍能解，前缀都是 `enc:v1:`。解不开（`SECRET_KEY` 换过或密文坏了）按空凭证处理，并在故障状态变化时打一条 WARNING，不打密文内容。管理端「集成密钥」「邮箱设置」的密钥只写：响应里恒为空串，另给 `*_set`（长 token 再给末 4 位 `*_hint`，口令不给）；保存时留空保留原值，`clear_<字段>: true` 才清空。Pelican / RCON「测试连接」只在地址与已存地址相同时才带上已存密钥，改了地址须重填
- 请求 ID：中间件生成或转发 `X-Request-ID`，写入日志上下文并回写响应头。何时打 logger 见 [`logging.md`](logging.md)
- CSP：默认 `Content-Security-Policy-Report-Only`（`report-uri /api/csp-report`）；`CSP_ENFORCE=true` 后 enforce。`/api/csp-report` 公开：请求体 ≤64KB（超限 413）；不逐条打日志，按「指令 + 被拦来源（只留 scheme://host）」进程内计数，首条立即、之后至多每分钟一条 WARNING 汇总（前 10 项 + 其余条数），不记完整 URL 与 query。`/uploads/*` 不论 `CSP_ENFORCE` 都带强制 `Content-Security-Policy: default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; sandbox`：上传文件即使被当成顶层文档打开也跑不了脚本，`<img>` 引用与浏览器的图片 / PDF / 纯文本查看不受影响；响应自带强制 CSP 时中间件不再叠站点策略（Report-Only 也不叠）
- 浏览器 RUM：`POST /api/client-rum` 公开（访客可报，便于统计攻略页），不校验 CSRF（`sendBeacon` 带不了自定义头），不落用户 id。限流 60 批/IP/10 分钟，每批最多 80 条，请求体 ≤256KB，一批一条批量 INSERT；URL 归并后去掉 query。管理端 `GET /api/settings/rum` 需管理员，接口按侧栏业务分类。样本 14 天后由 `job_runs_prune` 删除
- 请求体上限：`BodyLimitMiddleware`（栈最内层，在 SetupRequired 之后）对 `/api/*` 默认 8MB；上传接口按各自业务上限另留 1MB 表单余量（文件管理 256MB、Minecraft 文件 64MB、头像 5MB、酒馆附件 10MB、公式识别 2MB、塔科夫截图识别 8MB），`/api/client-errors` 64KB。`Content-Length` 超限直接 413，不读 body；无长度的分块请求边读边数，超限即 413。反代 `client_max_body_size` 应不小于最大上传
- 安装向导：未配库，或库里没有管理员且从未完成过初始化时，服务在 `DATA_DIR`（默认 `data/runtime/`）写一次性令牌文件 `setup-token`（启动或首次打开向导时生成，权限 600），日志只用 WARNING 打文件路径，不打令牌。`POST /api/setup/database`、`POST /api/setup/admin` 须带请求头 `X-Setup-Token`（该文件内容），缺失或不对回 403；`GET /api/setup/status` 的 `token_required` 告诉前端要不要填。建好首位管理员即删令牌文件，并在进程内补跑库就绪后的启动步骤（调度等），不必重启。已有管理员或写过完成标记（`system_configs` 的 `setup_completed`）一律 409。连库失败只回「无法连接数据库，请检查主机、端口、库名与账号密码」，驱动原文去掉口令后只进服务端日志
- 完成过初始化后管理员全没了（例如手工改库）：向导不再开放，启动打 WARNING。恢复二选一：在库里删掉 `system_configs` 中 `key='setup_completed'` 的行后重启，再走向导（令牌文件路径见日志）；或临时设进程环境变量 `ALLOW_ENV_ADMIN_SEED=true` 与 `ADMIN_*` 重启播种管理员（同名用户已存在则只提为管理员、不改口令），恢复后去掉
- 生产在管理端「运行环境」或 `config/app.json` 设置 `APP_ENV=production`（安装脚本**不会**代写）：管理员弱口令默认**拒绝启动**（对库内管理员做常见弱口令探测）。本地 `development` 仅 WARNING；可在管理端「安全设置」覆盖。在「运行环境」保存 `APP_ENV=production` 前，服务端按生产口径先跑同样两项启动体检（`ALLOW_EMAIL_CODE_LOG`、管理员弱口令，弱口令是否拒绝按「安全设置」与 `REJECT_WEAK_ADMIN_PASSWORD`，都没设时按生产默认拒绝）；会让重启失败就 400「生产环境启动体检未通过（保存后重启会拒绝启动）：…」列出原因，什么都不写
- 运行环境（`APP_ENV`、`REDIS_URL`、CORS、`CSP_ENFORCE`、`TRUST_X_FORWARDED_FOR`、`RATE_LIMIT_ENABLED`、`DATABASE_URL`）：进程环境变量优先于 `config/*.json`。由环境变量设定的项在管理端「运行环境」只读（`GET /api/settings/runtime-env` 的 `env_locked` 列出字段名），`PUT` 改这些值回 409（原样带回不算改），须在服务器上改环境变量后重启。`redis_url` 只回 `scheme://主机:端口/库号`，账号口令与查询串都不回（redis-py 也从查询串读 `password=`），是否配置、是否带口令看 `redis_url_set` / `redis_password_set`。保存时留空保留原值，`clear_redis_url: true` 才清空；回传的脱敏地址主机、端口与已存的一致（且没带账号口令或查询串）就沿用已存的账号口令与查询串，换了主机或端口按提交的原样存，已存口令不跟去别的服务器。「测试 Redis」同样只在主机端口一致时补上已存口令
- 限流与短时 KV（扫码会话、森空岛 cred 缓存、塔科夫联机 join/大厅）：生产建议在运行环境设 `REDIS_URL`；本地无 Redis 时进程内降级。多 `app` 实例须共享同一 Redis。滑动窗口限流受 `RATE_LIMIT_ENABLED` 控制（默认开，超限 429；只在排障或压测时临时关）。默认**不**信任 `X-Forwarded-For`（防伪造绕过）；置于受信反代后可在运行环境打开 `TRUST_X_FORWARDED_FOR`，此时取该头**最右一段**（紧邻反代看到的对端），客户端自己塞进去的前几段不算数
- 账号相关限流（`auth_limiter`，窗口都是 10 分钟）：登录 20/IP（账号维度只走下方失败退避，别人乱输锁不住本人）；QQ 登录发起 20/IP，换票 30/IP；QQ 绑定发起 20/IP、10/账号；注册发码与注销发码共用 10/IP、5/邮箱（注销另限 5/账号），重发、找回发码同样 10/IP、5/邮箱；绑定邮箱发码 10/IP、5/账号、5/邮箱；注册 10/IP、10/邮箱；邮箱验证 20/IP、10/邮箱；重置口令 10/IP、10/邮箱；绑定邮箱 20/IP、10/账号、10/邮箱；关联已有账号 20/IP、10/账号（校验目标口令另与登录共用失败退避）；注销 10/IP、10/账号；改密、改用户名各 10/账号
- 登录失败退避（不受 `RATE_LIMIT_ENABLED` 影响）：按「登录框填的账号 + 客户端 IP」计（邮箱、用户名各算各的，不分大小写），同一账号同一 IP 连错 4 次后，每再错一次锁 1、2、4、8 分钟…封顶 15 分钟；锁定期内直接 429，不再校验口令。别人从别的 IP 乱输锁不住本人。账号维度只设高得多的上限（换 IP 撞库）：各 IP 累计错满 50 次（中间没停过 1 小时），整号锁 5 分钟、计数重来。关联已有账号校验目标口令与登录共用这两套计数。登录成功只清本 IP 的计数；找回重置（证明了邮箱归属）连账号维度一起清。最后一次输错 1 小时后自动归零。计数在短时 KV（Redis `INCR`+`EXPIRE`，进程内加锁递增，并发失败一次不漏），键是账号与 IP 的哈希
- Redis 客户端：连接与读写超时 2s，`health_check_interval` 30s，超时重试一次；连不上时调用方回落进程内，30s 后再试连（不会因一次失败永久降级），等锁超过 0.5s 也先回落，不卡请求线程。故障只在状态变化时打一条 WARNING（URL 里的口令脱敏），恢复后打 INFO
- 本地无 SMTP 时需设 `ALLOW_EMAIL_CODE_LOG=true` 才能用日志收验证码；`APP_ENV=production` 时启动会硬拒绝该开关，在「运行环境」切到生产时也会先被拦下
- 勿提交 `config/`、`data/`、`var/`、`uploads/`。站点设置权威源是安装根 `config/*.json`（目录 700 / 文件 600）。模板在 `scripts/config.example/`；`install` / `run` / `restart` / `update` 与启动按文件 `_version` 补缺失键，不覆盖已有值（含密钥），也不会用模板新建 `database.json`。存量根 `.env` 只作一次性迁入，迁完可删。绑定凭证继续 Fernet 加密入库。`SECRET_KEY` 仍自动写 `data/runtime/.secret_key`

## 战鸽酒馆

公开页 `/tavern`、`/tavern/:slug`（未登录可看列表、正文、评论；页面走工作台 `AppLayout` 侧栏/顶栏）。写文章须酒馆作者或管理员；发表评论须登录。

- **读权限**：`GET /api/articles` 与分类/标签/**已发布**详情/评论不要求登录 Cookie / Bearer
- **写权限**：发改删文章、上传配图/附件、公式识别、版本恢复：酒馆作者（只动自己的稿）或管理员；删评与作者名单、全量文章列表走管理员；`POST .../comments` 须登录
- **删除**：文章为物理删除（行与评论 / 版本一并去掉），不可恢复
- **限流**（`platform_limiter`；生产靠 `REDIS_URL`）：评论 20/IP/10 分钟、10/账号/10 分钟；发稿 / 改稿 / 配图与附件 40/IP/10 分钟、20/账号/10 分钟；公式识别 10/IP/10 分钟、6/账号/10 分钟。公式识别另在进程内同时只跑 1 路，占不到就 429「已有识别任务在运行，请稍后再试」，不解图
- **正文**：`body_format=html` 入库前经 `nh3` 消毒（去 script / 事件 / `javascript:`），并只保留文章排版 class（对齐 / 缩进 / 调色板 / 高亮 / 公式源）；Markdown 仍由前端 `rehype-sanitize` 渲染。公式只存 LaTeX（`article-math` / `article-math-block`），阅读页再用 KaTeX（`trust: false`）渲染，不入库 KaTeX HTML。识别图只进内存，不落 `uploads/`
- **封面**：只允许 `http(s)` 或站内 `/uploads/...`
- **配图 / 附件**：只挂载 `/uploads/articles`（与头像一样，不暴露整个 upload 根目录）。图片按内容识别 JPG/PNG/WebP/GIF（≤5MB）；附件只收白名单扩展（文档/压缩包等，≤10MB）且校验魔数，拒绝 exe / html / svg。上传在工作线程里读，最多读到上限多 1 字节即判超限，不把整份读进内存。图片（含公式识别图、头像）先看文件头声明的尺寸，超过 2000 万像素直接 400「图片尺寸过大」、不解像素；解码只认 PNG / JPEG / WebP / GIF / BMP，EPS 等格式一律不解。落盘进 `user_files`（流水号 `serial` + 相对路径）；公开 URL 仍是 UUID 路径，**不要**把流水号写进 StaticFiles 路径。管理端「文件管理」只扫盘，不按流水号删文件
- **站内头像**：裁剪为正方形 JPEG 后覆盖写 `avatars/{member_id}.jpg`，登记同一张 `user_files`（`namespace=avatars`）。公开 URL 仍是 `/uploads/avatars/{id}.jpg?v=`，**不要**把流水号写进路径。删头像或注销标 `deleted` 并清盘
- 功能开关 `tavern`（任务配置「战鸽数据」；与站点模型更新同组）；关闭后公开 API 403、侧栏「社区」隐藏

## 塔科夫图鉴与工具

公开页 `/guides/tarkov`（未登录可看首页、物品/弹药/地图/商人/BOSS、任务目录与详情、搜索、藏身处目录百科、钥匙分类百科、工作台读枪/算属性/枪匠求解/社区方案、三狗状态、联机大厅列表与房间预览）。个人中心六个 Tab、OCR、出图代理、创建/加入房间与房间 WS 须登录；页内用登录卡，不整站踢去 `/login`。Minecraft 仍须登录。

- **读权限**：图鉴 GET、搜索、工作台 `allowed-items` / `calculate` / `community-builds` / `gunsmith-solve`、三狗 GET、大厅列表与房间预览不要求登录 Cookie / Bearer。仍 `require_feature("guides.tarkov")`。非成员（含未登录）`GET` 房间只回预览，不含棋盘/人员
- **写权限**：资料 / 藏身处等级 / 钥匙拥有 / 3×4 / 任务进度（完成、进行中、失败、小步骤） / 日志摘要 / 云端 raid-prep state / 地图筛选喜好、OCR、`build-image`、创建加入房间须登录
- **限流**（`platform_limiter`；生产靠 `REDIS_URL`）：搜索 40/IP/分钟；工作台 allowed/calculate 60/IP/分钟；community-builds 30/IP/10 分钟；gunsmith-solve 20/IP/分钟；三狗 40/IP/分钟；大厅列表 40/IP/分钟（登录用户另计账号）
- **回源**：只拉 json.tarkov.dev 全文件 dump。定时整站同步、管理员同步、各栏目同步与读接口的冷启动补拉共用进程内单飞锁，同一时刻只有一路回源。读接口碰上库里还没有该栏目 dump 时最多等锁 3 秒，仍在回源就 503「数据同步中，请稍后再试」并带 `Retry-After: 30`。管理员 `POST /api/guides/tarkov/sync` 转后台执行，立即 202 返回执行记录 `run_id`（进度与各栏目结果在「任务管理」`tarkov_full_sync`）；已有回源在跑时它和各栏目 `.../sync` 都回 409。定时整站同步碰上已有整站同步在跑就直接跳过，否则最多等锁 10 分钟；等锁期间别处开始过一轮整站同步，或始终等不到锁，都跳过。锁只管单个进程，多个 app 实例各自回源、互不排斥
- **截图识别**（钥匙箱、局前任务）：两者共用进程内 1 路识别槽，先占槽再解图，占不到直接 429「已有识别任务在运行，请稍后再试」。截图 ≤8MB；解码前按文件头尺寸拒掉超过 2000 万像素的图（400「图片尺寸过大…」），只认 PNG / JPEG / WebP / GIF / BMP
- **三狗 WebSocket**：握手 `Origin` 规则同「塔科夫联机」；首帧 10 秒内带登录令牌，否则 4401；客户端单帧 ≤16KB（超限 1009），ping 按令牌桶限速；推送 5 秒发不出去即断开（1013）
- 功能开关 `guides.tarkov`；关闭后公开 API 403。访客侧栏靠 `allowGuest` 露出入口，不打需登录的 `/platform-features/effective`

## 塔科夫联机

公开页 `/legal/terms`、`/legal/privacy`（未登录可看；文案在 `frontend/src/lib/legalDocs.ts`）。邮箱注册须勾选同意；登录 / QQ 登录旁注明即表示同意。页脚备案号由运营者配置（管理端「安全设置」），留空不展示。

- **读权限**：未登录可看大厅列表。未入座（含未登录）`GET /api/guides/tarkov/raid-rooms/{id}` 只回预览：标题、`game_mode`、是否上大厅、人数、`max_members`、是否要密码、`created_at`、`is_host`（`is_member=false`）。房间级 `map_slug` 恒为空。不含人员名单、房主 user_id、认领、标点、钥匙、目标完成、进度重叠、各人查看图。公开大厅列表展示在座昵称，以及每人当前地图和相位（战局 / 匹配用进程内日志相位里的图，否则用查看图；不入库）。房间 WebSocket 须已入座。在线标记带端类型：浏览器报 `web`，战鸽助手嵌入报 `desktop`；同一账号任一端连着即在线。端类型不进大厅列表。访客不能占座
- **写权限**：认领 / 标点等须在座；密码只在 **join** 时校验。公开或私密在创建时确定，之后不能改。私密房可不设密码，设了须 4–32 个字符（否则 400）。房间事务在进程内串行到提交为止；撞唯一键（并发占座、重复声明）整笔重跑一次，仍冲突回 409「房间状态刚变过，请刷新后重试」
- **限流**（`platform_limiter`；生产靠 `REDIS_URL`）：创建 20/IP/10 分钟、10/账号/10 分钟；加入（含密码错误）10/IP+房间/10 分钟、10/账号+房间/10 分钟；大厅列表 40/IP/分钟、40/账号/分钟
- **房间 WebSocket**：握手先校验 `Origin`，须是本站 Host（含 `X-Forwarded-Host`）、`PUBLIC_FRONTEND_URL` / `PUBLIC_BACKEND_URL`、`CORS_ORIGINS` 或当前 CORS 正则，否则 4403；不带 `Origin` 的非浏览器客户端放行，仍靠首帧令牌。首帧须在 10 秒内带令牌，否则 4401；未入座 4403，房间不存在 4404。单帧 ≤256KB（超限 1009 断开）；ping、切查看图、草图、坐标、日志相位各有令牌桶，超出的帧直接丢弃。推送 5 秒发不出去视为慢消费者，断开（1013）。入站事件距上次复核满 10 秒就回库再查一次座位。离座 / 被移出在事务提交后先给该成员已连的 socket 发 `member_leave`，再以 4403 关闭；房间解散（最后一人离开、座位过期回收后无人，或房主清空）在提交后发最后一帧，再以 4404 关闭全部 socket
- **大厅查询**：只加载当前顶栏模式、`listed` 且无密码、仍有人在座的房；过期座位按 `last_seen` 定向回收，不把全部房间扫进内存
- **日志**：客户端本机解析；同步后在浏览器审阅（日志行、任务名、状态变更），原文不入库。库表 `tarkov_user_raid_logs` 只存摘要。离线战局手选地图只在本机 localStorage。截图坐标只广播数字，不传图片；最近一次坐标留在进程内存，供同房间晚加入的入座成员（含同一账号的其他设备）从 WS snapshot 拿到，不落库

## Minecraft

Minecraft 页（Pelican 面板 + RCON）：状态、在线与性能须登录；文件、模组、启动指令与控制台只给管理员。

- **控制台 WebSocket**：握手 `Origin` 规则同「塔科夫联机」；首帧 10 秒内带令牌，否则 4401；非管理员或功能关闭 4403，未配置 Pelican 4000。浏览器单帧 ≤16KB，超长帧不解析直接 1009 断开；单条命令 ≤1024 字符且不含换行 / 空字符，否则不转发
- **上传**：≤64MB，在工作线程里最多读到上限多 1 字节即判超限，不把整份读进内存
- **模组安装 / 核心下载**：先让面板拉到同目录临时名 `*.zhange-part`（加载器只认 `*.jar`），再经签名 URL 读回校验：Modrinth 给了 sha512 就比对；没给的模组与 Arclight 核心至少确认是完整 jar（逐条目 CRC、解压总量 ≤1GB，核心还须带 MANIFEST）。校验通过才替换同名文件，新文件落位后才删旧版本；失败只删临时文件，旧文件不动。经签名 URL 读 jar 一律边读边数，超过上限（模组 96MB、核心 128MB）立即断开
- **RCON**：回包长度按原版分片上限（4096 字符，UTF-8 下最多 3 倍字节）校验，超长即断开重连；多片回包用哨兵包收齐，不靠超时猜末片；空闲连接上读到残留数据就丢掉重连，不复用读位置不可信的连接

## 文字识别

引擎、权重与场景选择是站点能力（`config/ocr.json`，管理端「站点设置 → 文字识别」）。上区一族一张卡（熊猫 OCR / EasyOCR），下区业务勾选族并设多端校验。熊猫档位从本机 RapidOCR `default_models.yaml`（onnxruntime）摊开。**没有**对外 `POST /api/ocr/recognize`；业务只走内部 Python 接口。权重在 `data/models/rapidocr` 与 `data/models/easyocr`，由本页「检查更新」或任务配置「文字识别模型」（`ocr_model_sync`）按当前 Paddle 档位预拉；识别时不现场下载。未就绪返回 503。公式识别（TexTeller）仍独立，走任务配置「公式识别模型」，不并进这套引擎。

## 文件管理

管理端「运行维护 → 文件管理」只给管理员：统计本站运行时 / 模型 / 缓存 / 依赖占用，并在**安装根**内增删改查（其下的 `data/` / venv / `node_modules` / 备份等点进去即可）。占用桶与磁盘采样都只计安装根内路径；站外缓存、家目录、`ZHANGE_BACKUP_DIR` 指向站外时不进目录树、不计入占用。进程内会把 Hugging Face / Torch / EasyOCR / pip / tempfile 指到安装根 `data/cache` 与 `data/tmp`，避免写到用户家目录。启动时把家目录里战鸽能认的权重（TexTeller hub、EasyOCR `.pth`）拷进安装根；不搬整个 `~/.cache/huggingface`（可能混有其它工具）。**禁止**把查询参数当成任意绝对路径；越出安装根返回 400。`.secret_key`（含写入中途的 `.secret_key.*` 临时文件）、`.env`（不含 `.env.example`）、密钥类后缀、明文带口令/密钥的 `config/database.json` / `config/integrations.json` / `config/email.json`（含 `write_json` 的 `.<名>.*.tmp`）、`data/mariadb/data` 与 `data/mariadb/provision.json`、以及站点备份 `zhange-*.tar.gz` / `zhange.sql` 列出时置灰：MariaDB 数据目录不可进入，这些文件不可下载、修改、上传覆盖、重命名或删除；也不能新建同名敏感项。用 SQLite 时，当前配置的库文件（默认 `data/runtime/zhange.sqlite`）及同名 `-wal` / `-shm` / `-journal` 同样置灰，也不可下载：WAL 下最近的提交还在 `-wal` 里，单拷主文件不是一致快照，删掉或换掉旁路文件会丢这些提交，库里还有口令散列与加密的平台凭证；要副本请跑 `backup` 脚本（走 SQLite 在线备份接口），删 `data/runtime/` 等目录时这几份原样留下。判定同时看请求路径和 `resolve` 之后的真实路径。符号链接与 Windows 目录联接（junction）在 `resolve` 之前逐级判定：列表里不列出；请求路径上任一级是链接一律 400（浏览、下载、读写、上传、新建、重命名、删除，含链接本身），在链接的名字上新建、上传或改名过去回 409，删除目录时其中的链接原样留下、不跟进，所以链接不能把 `config/`、MariaDB 数据目录或备份换个名字绕过去。`.git`、`config/` 等普通目录可进入、可删（`config/` 是活站点设置，删了站点会停；其中的 `app.json` 等普通设置可编辑）。删除普通目录时跳过其中的敏感子项（删 `config/` 会留下上面三份）。文本编辑 ≤2MB，上传 ≤256MB：上传接口在工作线程里把表单临时文件按块流式写到目标目录的 `.zhange-write-*.part`，边写边计数，超限 413，写完 fsync 再 `os.replace` 落位（覆盖时保留原权限位）；超限或出错不留半截文件，也不动原文件。编辑保存与新建文件走同一套原子写。塔科夫图鉴 dump 在数据库，Minecraft 服文件在 Pelican，都不走这套本机浏览。Pelican 的 401/403 以 502 返回，避免前端把面板密钥问题当成战鸽会话失效而整站登出。用户上传元数据在 `user_files`（按流水号查路径；酒馆 UUID、头像覆盖 `member_id.jpg`），不要和管理端盘点混成一个「文件服务」；从盘上删附件不会改登记表。

## 塔科夫钥匙截图识别

钥匙管理「截图识别」把用户粘贴的钥匙箱截图 `POST` 到本站，按 360–640（最佳约 540）正方形切块，按「文字识别」里为场景 `tarkov_keys` 勾选的引擎读格子 **shortName**（默认熊猫 OCR + EasyOCR）。每族另走反色补召回；该业务默认开启多端校验，模糊匹配须两个不同模型族同时读到，才放宽阈值。切块与闭集匹配仍在塔科夫业务里。响应只带回文本框坐标供覆盖层，原图与切块只进内存，不落 `uploads/`、不入库。确认后才 `merge` 到 `tarkov_user_key_owns`。限流：8/IP/10 分钟、6/账号/10 分钟；进程内同时只跑 1 路识别，客户端断开后工作线程在下一刀切块前退出。

## 塔科夫工作台出图

工作台中间用 dump 枪图做底板，在图上点槽位换配件。第三方出图接口默认关闭（`TARKOV_WORKBENCH_IMAGE_GEN=false`）。若手动打开，限流仍为出图 `POST /api/guides/tarkov/workbench/build-image` 40/IP/10 分钟、20/账号/10 分钟；返回的 `image_url` 只接受 `image-gen.tarkov-changes.com`。

## 塔科夫工作台社区方案

选枪后可浏览 EFTForge **公开**社区方案（`GET /builds/public?gun_id=`）。只读列表，投影成本站 dump 可装的 `pairs`；不落库（短时 KV 缓存原始 JSON）、不代投票/评论、不热链对方卡图。对方仓库为 MIT，社区用户内容按公开列表展示并署名来源。关闭：`TARKOV_WORKBENCH_COMMUNITY=false`。限流：`GET /api/guides/tarkov/workbench/community-builds` 30/IP/10 分钟（公开接口，只按 IP）。

## 塔科夫工作台枪匠求解

枪匠改装目标从本站 tasks dump 的 `buildWeapon` 投影，不 vendor 第三方任务包。`POST /api/guides/tarkov/workbench/gunsmith-solve` 在工作台索引上做约束满足；限流 20/IP/分钟（公开接口，只按 IP）。求解入口在本站任务详情与地图右侧任务卡，结果只在工作台展示。

对外宣传前的环境核对见 [`deploy.md`](deploy.md)「公开运营检查」。

平台数据约定（养成盒 / 旁路 raw、签到展示始终 force 回源）见 [`.cursor/rules/platform-raw-cache.mdc`](../.cursor/rules/platform-raw-cache.mdc)。森空岛官服/B服与补奖见 [`.cursor/rules/skland-upstream.mdc`](../.cursor/rules/skland-upstream.mdc)。
