# 战鸽数据 · Zhange Stats

**v0.2.0** — OpenAPI 契约对齐、安全与健康检查加固、Agent 治理落地、深度清理死代码。

## 功能

- 邮箱注册 / 登录（JWT）；管理员与普通用户；支持 QQ 互联登录 / 绑定
- Steam OpenID 绑定、自定义头像、Steam 日历（日时间轴 + 周/月/年热力；仅自己与 Steam 好友）
- 我的日常：本人各平台签到任务与日志；管理端任务配置按平台 / 游戏 / 任务级联开关
- 管理端：用户 / 集成密钥（含 NapCat）/ QQ 群 / 邮箱 / 可配置定时任务
- 森空岛绑定与每日自动签到（明日方舟、明日方舟：终末地）
- 明日方舟干员盒子对比（多渠道服、练度悬浮、日更缓存）；终末地盒子 raw 缓存；开源图鉴同步
- 塔吉多绑定与每日自动签到（异环）
- 追放社区绑定、签到、每日任务与积分兑换
- 库街区绑定与每日自动签到（社区 + 鸣潮 / 战双）
- Docker 部署后由 **Watchtower** 自动拉取新镜像

## 技术栈

| 端 | 技术 |
|---|---|
| 前端 | React 18 · TypeScript · Vite · Ant Design 5 · TanStack Query · Zustand |
| 后端 | FastAPI · SQLAlchemy 2 · Alembic · APScheduler · MySQL · JWT / bcrypt |

## 本地开发

需要 Python 3.11+、Node 18+、MySQL：

```sql
CREATE DATABASE zhange_stats_dev CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
-- 生产库另建：CREATE DATABASE zhange_stats CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

```bash
cp .env.example .env   # 至少填 DATABASE_URL；JWT 密钥自动生成
```

首次打开站点会进入 **安装向导** 创建管理员。邮件 SMTP、Steam/QQ 密钥、登录有效期 / 口令策略、签到与轮询调度：登录后在侧栏 **管理** 配置（写入 `system_configs`）。CI 可用 `ALLOW_ENV_ADMIN_SEED=true` + `ADMIN_*` 跳过向导。

```bash
# 后端
cd backend && python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# 前端（另开终端）
cd frontend && npm install && npm run dev
```

- API：http://127.0.0.1:8000/docs · 前端：http://127.0.0.1:5173  
- 启动时自动 `alembic upgrade`；改表：`alembic revision --autogenerate -m "..."`（见 `backend/alembic/README.md`）  
- 环境变量说明见 `.env.example`。Steam/QQ 回调与 CORS 默认按访问 Host 自动推断；QQ 互联后台登记的回调须与「实际打开站点的地址」一致（集成密钥页可复制）。密钥与头像目录由程序默认创建（本地 `data/`、`uploads/`；Docker 挂载 `./data`）。  
- 平台可用性：管理员在 **系统管理 → 任务配置** 按平台 / 游戏 / 任务级联开关

## Docker

镜像只含应用，**MySQL 自备**。复制 `.env` 后：

```bash
docker compose pull && docker compose up -d
# 浏览器 http://<主机>:8080 （前后端同域，OAuth 回调按访问地址自动推断）
```

数据卷：`./data`（含 `.secret_key`）、`./data/uploads`（头像）。

发版：推送到 `main` 时构建一次，镜像标签为 **`VERSION` 文件版本号** + `latest`（例如 `0.2.0` 与 `latest`）。不必再推 `v*` 标签来触发构建；Watchtower 默认跟踪 `latest`。

**自动更新**：`compose.yml` 含 Watchtower，默认每 5 分钟检查 `app` 镜像；CI 推送新 `latest` 后会自动 pull 并重建。

## 目录

```
zhange-stats/
  compose.yml · Dockerfile · .env.example · VERSION
  frontend/                 # React
  backend/app/              # api · core · models · services
  backend/alembic/          # 迁移（表结构以 versions/ 为准）
```

## 数据库

改表须新增 Alembic 迁移，并更新本节总览。细节以 `models/` + `alembic/versions/` 为准。

```
users 1 ── 1 members ── * play_sessions / presence_segments / steam_friend_edges
                      └── 0..1 skland_binds ── * skland_checkin_logs
                                         └── * skland_attendance_raws
                                         └── * endfield_box_raws
                                         └── * arknights_box_snapshots
                      └── 0..1 taygedo_binds ── * taygedo_checkin_logs
                                         └── * taygedo_attendance_raws
                      └── 0..1 exilium_binds ── * exilium_checkin_logs
                      └── 0..1 kujiequ_binds ── * kujiequ_checkin_logs
                      └── * checkin_role_prefs（按平台/角色自动签到）
system_configs · register_challenges · oauth_exchange_tickets · job_runs · steam_apps
arknights_operators · arknights_catalog_meta
```

| 表 | 用途 |
|---|---|
| `users` | 账号、`role`（权限唯一来源）、邮箱验证；API 仍返回派生字段 `is_admin` |
| `members` | 档案、站内头像/昵称、Steam 绑定（含 `steam_persona_name` / `steam_avatar_url`）、QQ 互联（`qq_openid` 等）与 `qq_number`（群成员匹配） |
| `steam_friend_edges` | 好友缓存（日历仅好友可见）；`member_id` ON DELETE CASCADE |
| `play_sessions` | 游戏中会话（热力）；索引含 `(member_id, started_at)` / `(member_id, ended_at)`；`member_id` ON DELETE CASCADE |
| `presence_segments` | 离线/在线/游戏中（日时间轴）；索引含 `(member_id, started_at)` / `(member_id, ended_at)`；`member_id` ON DELETE CASCADE |
| `skland_binds` | 森空岛凭证（加密）；`auto_checkin` 为各角色偏好派生摘要；`checkin_hour` / `checkin_minute` 仅作旧数据种子 |
| `checkin_role_prefs` | 各平台按角色的自动签到开关与北京时间（`platform`+`game_code`+`role_uid`） |
| `skland_checkin_logs` | 森空岛角色签到记录（按「今日」缓存读优先；含 `awards_text` / `awards_json`；超期由 `job_runs_prune` 清理） |
| `skland_attendance_raws` | 明日方舟签到日历 GET attendance 原始 JSON（按 member+uid 最新一份；跨月或 force / 签到后回源） |
| `endfield_box_raws` | 终末地 card/detail 原始 JSON（按 role 最新一份） |
| `arknights_operators` | 明日方舟干员图鉴（自开源 character_table 同步） |
| `arknights_catalog_meta` | 图鉴同步元数据（单行，含版本与同步时间） |
| `arknights_box_snapshots` | 明日方舟盒子练度快照（按 member + uid 日更；`payload_json` LONGTEXT） |
| `taygedo_binds` | 塔吉多凭证（加密）；`auto_checkin` 为角色偏好派生摘要 |
| `taygedo_checkin_logs` | 塔吉多 / 异环签到记录 |
| `taygedo_attendance_raws` | 异环 / 幻塔签到日历（signin/state + sign/rewards）原始 JSON（按 member+game+role 最新一份；跨月或 force / 签到后回源） |
| `exilium_binds` | 追放社区凭证（加密）；`auto_checkin` 为角色偏好派生摘要 |
| `exilium_checkin_logs` | 追放社区签到记录 |
| `kujiequ_binds` | 库街区凭证（加密）；`auto_checkin` 为角色偏好派生摘要 |
| `kujiequ_checkin_logs` | 库街区社区 / 鸣潮 / 战双签到记录 |
| `job_runs` | 轮询 / 签到等任务执行日志；与 `*_checkin_logs` 默认保留 90 天，由定时任务 `job_runs_prune` 清理 |
| `system_configs` | 系统配置（SMTP、集成密钥、`platform_features` 平台开关、调度等） |
| `register_challenges` | 注册验证码 |
| `oauth_exchange_tickets` | QQ 登录一次性换票码（短 TTL，避免 JWT 进回调 URL） |
| `steam_apps` | Steam AppID → 显示名 / 库封面图标 / 头图 / 国区价格缓存 |

启动时会 DROP 已废弃表：`games` / `match_records` / `cs2_*`。

## 说明

- **Agent / 开发约定**：仓库根 [`AGENTS.md`](AGENTS.md)；Cursor 规则见 [`.cursor/rules/`](.cursor/rules/)（架构索引 always-on）。治理方案：[`docs/agent-governance-plan.md`](docs/agent-governance-plan.md)。
- 登录以邮箱为主，也支持 QQ 登录一键开号（回调只带一次性 `ticket`，前端再换 JWT）；无邮箱时可稍后完善
- 默认 JWT 有效期 **24 小时**（`ACCESS_TOKEN_EXPIRE_MINUTES` 或管理端「安全」可调；库内已存配置优先生效）
- JWT 目前存前端 `localStorage`（zustand persist）。后续若迁 **httpOnly Cookie**：需后端 `Set-Cookie`（`Secure`/`SameSite`）、登录/登出/QQ 换票改写、CSRF 策略，以及 SPA 同域部署前提；在完成 CSRF 方案前保持 Bearer header，避免半吊子改造扩大攻击面。
- 生产设置 `APP_ENV=production`（Docker 镜像默认已设）：管理员弱口令默认**拒绝启动**（对库内管理员做常见弱口令探测）。本地 `development` 仅 WARNING；可在管理端「安全设置」覆盖，或遗留 env `REJECT_WEAK_ADMIN_PASSWORD`。
- 限流默认进程内；多实例可设 `REDIS_URL`（需 `redis` 包，已列入 requirements）。
- 站内头像/昵称与 Steam 头像/昵称分离；Steam 页统计使用后者
- Steam 隐私过严时可能跳过本轮状态；未返回过久会超时收尾会话
- 森空岛支持扫码 / 短信 / 密码绑定，凭证加密存库；勿在 App 退出登录以免失效
- 塔吉多使用手机号验证码或密码登录老虎官方接口，凭证加密存库；用于异环 / 幻塔每日签到
- 库街区使用手机号短信验证码绑定，凭证加密存库
- 勿提交 `.env`、`data/`、`uploads/`

- 平台数据约定：养成盒存 raw（体积超阈值会打监控日志）；签到状态/奖励按「今日」写入 `*_checkin_logs`（权威详情），`bind.last_checkin_*` 仅为签到动作后的反规范化摘要。打开页优先读库，无今日记录或 `force` 才查官方。详见 [`.cursor/rules/platform-raw-cache.mdc`](.cursor/rules/platform-raw-cache.mdc)。
- 工程：GitHub Actions 在 PR/push 上跑前端 lint+build、后端 pytest、OpenAPI drift；`main` 推送再构建并推送 GHCR。API 变更后请执行 `npm run export:openapi && npm run gen:api`（见 `frontend/src/api/generated/README.md`）。
- 健康检查：`GET /health` 返回 `status` / `database` / `scheduler` / `version`（数据库不通时为 `degraded`）。
- 本地无 SMTP 时需设 `ALLOW_EMAIL_CODE_LOG=true` 才能用日志收验证码；生产勿开启。
