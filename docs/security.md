# 安全与运行注意

产品介绍见根 [`README.md`](../README.md)。部署形态与 Redis 多实例约束见 [`deploy.md`](deploy.md)「部署形态」。

- 登录以邮箱为主，也支持 QQ 登录一键开号（回调只带一次性 `ticket`，前端再换 JWT）；无邮箱时可稍后完善
- 默认 JWT 有效期 **24 小时**（`ACCESS_TOKEN_EXPIRE_MINUTES` 或管理端「安全」可调；库内已存配置优先生效）
- 新签发的 JWT：`sub` 为 **user_id**（数字字符串），另带 `username`。旧票 `sub` 仍是用户名，解码时按是否纯数字区分，登录态不中断
- JWT 目前存前端 `localStorage`（zustand persist）。后续若迁 **httpOnly Cookie**：需后端 `Set-Cookie`（`Secure`/`SameSite`）、登录/登出/QQ 换票改写、CSRF 策略，以及 SPA 同域部署前提；在完成 CSRF 方案前保持 Bearer header，避免半吊子改造扩大攻击面
- 平台凭证 Fernet 加密存库。QQ 回调不要把 JWT 放进 URL
- 生产设置 `APP_ENV=production`（`scripts/install.sh` 会写入）：管理员弱口令默认**拒绝启动**（对库内管理员做常见弱口令探测）。本地 `development` 仅 WARNING；可在管理端「安全设置」覆盖，或遗留 env `REJECT_WEAK_ADMIN_PASSWORD`
- 限流与短时 KV（扫码会话、森空岛 cred 缓存）：生产建议设 `REDIS_URL`；本地无 `REDIS_URL` 时进程内降级。多 `app` 实例须共享同一 Redis。默认**不**信任 `X-Forwarded-For`（防伪造绕过）；置于受信反代后可设 `TRUST_X_FORWARDED_FOR=true`
- 本地无 SMTP 时需设 `ALLOW_EMAIL_CODE_LOG=true` 才能用日志收验证码；`APP_ENV=production` 时启动会硬拒绝该开关
- 勿提交 `.env`、`var/`、`data/`、`uploads/`

平台数据约定（养成盒 / 旁路 raw、签到展示始终 force 回源）见 [`.cursor/rules/platform-raw-cache.mdc`](../.cursor/rules/platform-raw-cache.mdc)。森空岛官服/B服与补奖见 [`.cursor/rules/skland-upstream.mdc`](../.cursor/rules/skland-upstream.mdc)。
