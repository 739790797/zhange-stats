# 安全与运行注意

产品介绍见根 [`README.md`](../README.md)。部署形态与 Redis 多实例约束见 [`deploy.md`](deploy.md)「部署形态」。

- 登录以邮箱为主，也支持 QQ 登录一键开号（回调只带一次性 `ticket`，前端再换 JWT）；无邮箱时可稍后完善
- 默认 JWT 有效期 **24 小时**（`ACCESS_TOKEN_EXPIRE_MINUTES` 或管理端「安全」可调；库内已存配置优先生效）
- 新签发的 JWT：`sub` 为 **user_id**（数字字符串），另带 `username`。旧票 `sub` 仍是用户名，解码时按是否纯数字区分，登录态不中断
- JWT 目前存前端 `localStorage`（zustand persist）。后续若迁 **httpOnly Cookie**：需后端 `Set-Cookie`（`Secure`/`SameSite`）、登录/登出/QQ 换票改写、CSRF 策略，以及 SPA 同域部署前提；在完成 CSRF 方案前保持 Bearer header，避免半吊子改造扩大攻击面
- 平台凭证 Fernet 加密存库。QQ 回调不要把 JWT 放进 URL
- 生产设置 `APP_ENV=production`（`scripts/install.sh` 会写入）：管理员弱口令默认**拒绝启动**（对库内管理员做常见弱口令探测）。本地 `development` 仅 WARNING；可在管理端「安全设置」覆盖，或遗留 env `REJECT_WEAK_ADMIN_PASSWORD`
- 限流与短时 KV（扫码会话、森空岛 cred 缓存、塔科夫联机 join/大厅）：生产建议设 `REDIS_URL`；本地无 `REDIS_URL` 时进程内降级。多 `app` 实例须共享同一 Redis。默认**不**信任 `X-Forwarded-For`（防伪造绕过）；置于受信反代后可设 `TRUST_X_FORWARDED_FOR=true`
- 本地无 SMTP 时需设 `ALLOW_EMAIL_CODE_LOG=true` 才能用日志收验证码；`APP_ENV=production` 时启动会硬拒绝该开关
- 勿提交 `.env`、`var/`、`data/`、`uploads/`

## 塔科夫联机

公开页 `/legal/terms`、`/legal/privacy`（未登录可看；文案在 `frontend/src/lib/legalDocs.ts`）。邮箱注册须勾选同意；登录 / QQ 登录旁注明即表示同意。页脚展示 ICP 备案号 [浙ICP备2025147006号](https://beian.miit.gov.cn/)。

- **读权限**：未入座 `GET /api/guides/tarkov/raid-rooms/{id}` 只回标题、地图、人数、是否要密码（`is_member=false`）。不含人员名单、房主 user_id、认领、标点、钥匙、目标完成、进度重叠。公开大厅列表仍展示公开房的在座昵称。房间 WebSocket 须已入座
- **写权限**：认领 / 标点 / 设密等须在座；密码只在 **join** 时校验
- **限流**（`platform_limiter`；生产靠 `REDIS_URL`）：创建 20/IP/10 分钟、10/账号/10 分钟；加入（含密码错误）10/IP+房间/10 分钟、10/账号+房间/10 分钟；大厅列表 40/IP/分钟、40/账号/分钟
- **大厅查询**：只加载当前顶栏模式、`listed` 且无密码、仍有人在座的房；过期座位按 `last_seen` 定向回收，不把全部房间扫进内存
- **日志**：客户端本机解析；库表 `tarkov_user_raid_logs` 只存摘要。截图坐标只广播数字，不传图片

对外宣传前的环境核对见 [`deploy.md`](deploy.md)「公开运营检查」。

平台数据约定（养成盒 / 旁路 raw、签到展示始终 force 回源）见 [`.cursor/rules/platform-raw-cache.mdc`](../.cursor/rules/platform-raw-cache.mdc)。森空岛官服/B服与补奖见 [`.cursor/rules/skland-upstream.mdc`](../.cursor/rules/skland-upstream.mdc)。
