# 战鸽数据 · Zhange Stats

**v0.2.32** — CI 升到 Node 24 运行时，消除 oxlint Fast Refresh 注解。

## 功能

- 邮箱注册 / 登录（JWT）；管理员与普通用户；支持 QQ 互联登录 / 绑定
- Steam OpenID 绑定、自定义头像、Steam 日历（日时间轴 + 周/月/年热力；站内用户互看）
- 我的日常：本人各平台签到任务与日志；管理端任务配置按平台 / 游戏 / 任务级联开关
- 管理端：用户 / 集成密钥（含 NapCat）/ QQ 群 / 邮箱 / 可配置定时任务 / **系统更新**
- **攻略**：逃离塔科夫攻略站（全站搜索、物品分类、任务 / 商人 / BOSS、Tarkov Tracker 进度）；弹药穿透对照与枪械总表（定时自 tarkov.dev 同步）
- 森空岛绑定与每日自动签到（明日方舟、明日方舟：终末地）
- 明日方舟干员盒子对比（多渠道服、练度悬浮、日更缓存）；终末地盒子 raw 缓存；开源图鉴同步
- 塔吉多绑定与每日自动签到（社区 APP + 异环 / 幻塔）；社区每日任务与兑换
- 追放社区绑定、签到、每日任务与兑换
- 库街区绑定与每日自动签到（社区 + 鸣潮 / 战双）；兑换；鸣潮资料卡（roleBox raw 缓存）
- 生产（LXC）：管理端一键从 GitHub Release 更新代码与预构建前端

## 技术栈

| 端 | 技术 |
|---|---|
| 前端 | React 18 · TypeScript · Vite · Ant Design 5 · TanStack Query · Zustand |
| 后端 | FastAPI · SQLAlchemy 2 · Alembic · APScheduler · MySQL · JWT / bcrypt |

## 本地开发（Windows）

需要 Python 3.11+、Node 18+、MySQL：

```sql
CREATE DATABASE zhange_stats_dev CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
-- 生产库另建：CREATE DATABASE zhange_stats CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

```bash
cp .env.example .env   # 至少填 DATABASE_URL；JWT 密钥自动生成
```

首次打开站点会进入 **安装向导** 创建管理员。邮件 SMTP、Steam/QQ 密钥、登录有效期 / 口令策略、签到与轮询调度：登录后在侧栏 **管理** 配置（写入 `system_configs`）。CI 可用 `ALLOW_ENV_ADMIN_SEED=true` + `ADMIN_*` 跳过向导。

推荐用脚本（热重载）：

```powershell
run_dev.bat          # 双击启动（内部调用 scripts/dev.ps1）；另支持 stop / restart / status
run_dev.bat status
run_dev.bat stop
```

或手动：

```bash
# 后端
cd backend && python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 6130

# 前端（另开终端）
cd frontend && npm install && npm run dev
```

- API：http://127.0.0.1:6130/docs · 前端：http://127.0.0.1:6131  
- 启动时自动 `alembic upgrade`；改表：`alembic revision --autogenerate -m "..."`（见 `backend/alembic/README.md`）  
- 环境变量说明见 `.env.example`。Steam/QQ 回调与 CORS 默认按访问 Host 自动推断；QQ 互联后台登记的回调须与「实际打开站点的地址」一致（集成密钥页可复制）。密钥与头像目录由程序默认创建（本地 `data/`、`uploads/`）。  
- 平台可用性：管理员在 **管理 → 任务配置** 按平台 / 游戏 / 任务级联开关  
- **管理端一键更新仅面向 production / LXC**；Windows 开发机默认不可用（`APP_ENV=development`）

## 生产部署（Linux LXC，推荐）

单副本源码部署。MySQL / MariaDB 自备（塔科夫物品 raw 约 20MB，建议 `max_allowed_packet ≥ 64M`）；可选本机 Redis（限流 / 扫码 KV；不配则进程内降级）。

```bash
git clone https://github.com/739790797/zhange-stats.git /opt/zhange-stats
cd /opt/zhange-stats
cp .env.example .env   # 编辑 DATABASE_URL；建议 REDIS_URL=redis://127.0.0.1:6379/0
bash scripts/install.sh
# 编辑 .env 后：
sudo systemctl start zhange-stats
# 浏览器 http://<LXC>:8000 （或经反代）；安装向导创建管理员
```

更新方式（AstrBot 式，**仅管理端**）：

1. 管理端 → **系统更新** → 检查 / 一键更新  
2. 进程内下载 GitHub Release 源码 zip + 预构建 `static` → pip  
3. **`os.execv` 同 PID 换码**（无需 `systemctl`、无需 root）  
4. 安装树须属服务用户（`zhange`）可写；勿用 root 手改代码属主

应急排障（非常规升级路径）：`sudo systemctl restart zhange-stats`。

**部署形态**：单 `app` 进程。APScheduler、签到/Steam 进程内锁、启动时 Alembic 迁移均非多实例安全。水平扩展前须另行解决调度选举、共享 `DATA_DIR`/`SECRET_KEY`、迁移单点，以及共享 `REDIS_URL`。

发版：推送到 `main` 时 CI 按根目录 `VERSION` 创建/更新 GitHub Release（tag `v{VERSION}`），并上传 `zhange-stats-{VERSION}-static.tar.gz`。

持久化目录：`data/`（含 `.secret_key`）、`uploads/`、`.env`（更新白名单不会覆盖）。

## 目录

```
zhange-stats/
  .env.example · VERSION · scripts/install.sh
  deploy/systemd/zhange-stats.service
  frontend/                 # React
  backend/app/              # api · core · models · services
  backend/alembic/          # 迁移（表结构以 versions/ 为准）
```
## 数据库

改表须新增 Alembic 迁移，并更新本节总览。细节以 `models/` + `alembic/versions/` 为准。

```
users 1 ── 1 members ── * play_sessions / presence_segments
                      └── 0..1 skland_binds ── * skland_checkin_logs
                                         └── * skland_attendance_raws
                                         └── * endfield_box_raws
                                         └── * arknights_box_snapshots
                                         └── * arknights_rogue_raws
                      └── 0..1 taygedo_binds ── * taygedo_checkin_logs
                                         └── * taygedo_attendance_raws
                                         └── * exastris_box_raws
                      └── 0..1 exilium_binds ── * exilium_checkin_logs
                      └── 0..1 kujiequ_binds ── * kujiequ_checkin_logs
                                         └── * kujiequ_attendance_raws
                                         └── * kujiequ_ww_box_raws
                      └── * checkin_role_prefs（按平台/角色加入本站 + 自动签到）
system_configs · register_challenges · oauth_exchange_tickets · job_runs · steam_apps
arknights_operators · arknights_catalog_meta
tarkov_items_raws · tarkov_items_meta
tarkov_ammo · tarkov_ammo_meta
tarkov_guns · tarkov_gun_meta
tarkov_tasks_raws · tarkov_tasks_meta
tarkov_traders_raws · tarkov_traders_meta
tarkov_bosses_raws · tarkov_bosses_meta
tarkov_guides_raws · tarkov_guides_meta
tarkov_tracker_binds
```

| 表 | 用途 |
|---|---|
| `users` | 账号、`role`（权限唯一来源）、邮箱验证；API 仍返回派生字段 `is_admin` |
| `members` | 档案、站内头像/昵称、Steam 绑定（含 `steam_persona_name` / `steam_avatar_url`）、QQ 互联（`qq_openid` 等）与 `qq_number`（群成员匹配） |
| `play_sessions` | 游戏中会话（热力）；索引含 `(member_id, started_at)` / `(member_id, ended_at)`；`member_id` ON DELETE CASCADE |
| `presence_segments` | 离线/在线/游戏中（日时间轴）；索引含 `(member_id, started_at)` / `(member_id, ended_at)`；`member_id` ON DELETE CASCADE |
| `skland_binds` | 森空岛凭证（加密）；`auto_checkin` 为各角色偏好派生摘要；`checkin_hour` / `checkin_minute` 仅作旧数据种子 |
| `checkin_role_prefs` | 各平台按角色的「加入本站」(`included`) 与自动签到开关/北京时间（`platform`+`game_code`+`role_uid`）；签到页与调度仅处理 `included`；`enabled` 另控自动签到 |
| `skland_checkin_logs` | 森空岛角色签到记录（展示路径打开页始终回源后 upsert；`source`=`status` 查询 / `action` 真正执行，不驱动产品 UI；含 `awards_text` / `awards_json`；调度可按今日成功态跳过；超期由 `job_runs_prune` 清理） |
| `skland_attendance_raws` | 明日方舟签到日历 GET attendance 原始 JSON（按 member+uid 最新一份；跨月或 force / 签到后回源） |
| `endfield_box_raws` | 终末地 card/detail 原始 JSON（按 role 最新一份） |
| `arknights_operators` | 明日方舟干员图鉴（自开源 character_table 同步） |
| `arknights_catalog_meta` | 图鉴同步元数据（单行，含版本与同步时间） |
| `tarkov_items_raws` | 逃离塔科夫物品上游原始 JSON（全站最新一份；GraphQL split 或 json.tarkov.dev items；弹药/枪械共用；失败不覆盖） |
| `tarkov_items_meta` | 物品同步元数据（单行，含 ammo/gun 计数与同步时间） |
| `tarkov_ammo` | 弹药派生读模型（items raw parse；含 `ammo_type` / `icon_link` / 初速 / 精度·后坐·流血修正；供列表/散点） |
| `tarkov_ammo_meta` | 弹药展示元数据（单行；与 items 同事务写入） |
| `tarkov_guns` | 枪械派生读模型（口径/射速/人机/后坐/`allowed_ammo` 等） |
| `tarkov_gun_meta` | 枪械展示元数据（单行） |
| `tarkov_tasks_raws` | 逃离塔科夫任务上游原始 JSON（全站最新一份；GraphQL 或 json.tarkov.dev tasks + locale；失败不覆盖） |
| `tarkov_tasks_meta` | 任务同步元数据（单行，含 task_count 与同步时间） |
| `tarkov_traders_raws` | 逃离塔科夫商人上游原始 JSON（全站最新一份；json.tarkov.dev traders + locale + 物品 buyFromTrader 报价；失败不覆盖） |
| `tarkov_traders_meta` | 商人同步元数据（单行，含 trader_count / offer_count 与同步时间） |
| `tarkov_bosses_raws` | 逃离塔科夫 BOSS 上游原始 JSON（全站最新一份；json.tarkov.dev maps + mobs 精简包 + locale；失败不覆盖） |
| `tarkov_bosses_meta` | BOSS 同步元数据（单行，含 boss_count 与同步时间） |
| `tarkov_guides_raws` | 逃离塔科夫藏身处 / 以物易物 / 制作上游原始 JSON（全站最新一份；json.tarkov.dev hideout+barters+crafts + locale；失败不覆盖） |
| `tarkov_guides_meta` | 藏身处与交换同步元数据（单行，含 station_count / barter_count / craft_count 与同步时间） |
| `tarkov_tracker_binds` | 用户 Tarkov Tracker API token（Fernet 加密；摘要：等级 / 阵营 / 已完成任务数；`progress_json` 为每条任务 complete/failed；API 不回传明文 token） |
| `arknights_box_snapshots` | 明日方舟盒子练度快照（按 member + uid 日更；`payload_json` LONGTEXT） |
| `arknights_rogue_raws` | 明日方舟肉鸽 GET `/game/arknights/rogue` 原始 JSON（按 member+uid+topic 最新一份；force / 首次回源） |
| `taygedo_binds` | 塔吉多凭证（加密）；`auto_checkin` 为角色偏好派生摘要 |
| `taygedo_checkin_logs` | 塔吉多社区 APP / 异环 / 幻塔签到记录（`source` status/action；含 `awards_text` / `awards_json`） |
| `taygedo_attendance_raws` | 异环 / 幻塔签到日历（signin/state + sign/rewards）原始 JSON（按 member+game+role 最新一份；跨月或 force / 签到后回源） |
| `exastris_box_raws` | 异环 yh/characters 原始 JSON（按 member+role 最新一份；force / 首次回源） |
| `exilium_binds` | 追放社区凭证（加密）；`auto_checkin` 为角色偏好派生摘要 |
| `exilium_checkin_logs` | 追放社区签到记录（`source` status/action；含 `awards_text` / `awards_json`） |
| `kujiequ_binds` | 库街区凭证（加密）；`auto_checkin` 为角色偏好派生摘要 |
| `kujiequ_checkin_logs` | 库街区社区 / 鸣潮 / 战双签到记录（`source` status/action；含 `awards_text` / `awards_json`） |
| `kujiequ_attendance_raws` | 鸣潮 / 战双签到日历（initSignInV2 + queryRecordV2）原始 JSON（按 member+game+role 最新一份；跨月或 force / 签到后回源） |
| `kujiequ_ww_box_raws` | 鸣潮 roleBox（baseData + calabashData）组合原始 JSON（按 member+role 最新一份；force / 首次回源） |
| `job_runs` | 轮询 / 签到等任务执行日志；与 `*_checkin_logs` 默认保留 90 天，由定时任务 `job_runs_prune` 清理 |
| `system_configs` | 系统配置（SMTP、集成密钥、`platform_features` 平台开关、调度等） |
| `register_challenges` | 注册验证码 |
| `oauth_exchange_tickets` | QQ 登录一次性换票码（短 TTL；`access_token` Fernet 加密落库，避免 JWT 进回调 URL） |
| `steam_apps` | Steam AppID → 显示名 / 库封面图标 / 头图 / 国区价格缓存 |

迁移 `20260806_0026` 会一次性清空四平台 `*_checkin_logs` 并重置各 bind 的 `last_checkin_*`（表结构保留；打开页按新流程回源）。不可 `downgrade` 恢复数据。

启动时会 DROP 已废弃表：`games` / `match_records` / `cs2_*`。

## 说明

- **Agent / 开发约定**：仓库根 [`AGENTS.md`](AGENTS.md)；Cursor 规则见 [`.cursor/rules/`](.cursor/rules/)（架构索引 always-on）。治理方案：[`docs/agent-governance-plan.md`](docs/agent-governance-plan.md)。
- 登录以邮箱为主，也支持 QQ 登录一键开号（回调只带一次性 `ticket`，前端再换 JWT）；无邮箱时可稍后完善
- 默认 JWT 有效期 **24 小时**（`ACCESS_TOKEN_EXPIRE_MINUTES` 或管理端「安全」可调；库内已存配置优先生效）
- JWT 目前存前端 `localStorage`（zustand persist）。后续若迁 **httpOnly Cookie**：需后端 `Set-Cookie`（`Secure`/`SameSite`）、登录/登出/QQ 换票改写、CSRF 策略，以及 SPA 同域部署前提；在完成 CSRF 方案前保持 Bearer header，避免半吊子改造扩大攻击面。
- 生产设置 `APP_ENV=production`（`scripts/install.sh` 会写入）：管理员弱口令默认**拒绝启动**（对库内管理员做常见弱口令探测）。本地 `development` 仅 WARNING；可在管理端「安全设置」覆盖，或遗留 env `REJECT_WEAK_ADMIN_PASSWORD`。
- 限流与短时 KV（扫码会话、森空岛 cred 缓存）：生产建议设 `REDIS_URL`；本地无 `REDIS_URL` 时进程内降级。多 `app` 实例须共享同一 Redis。默认**不**信任 `X-Forwarded-For`（防伪造绕过）；置于受信反代后可设 `TRUST_X_FORWARDED_FOR=true`。**当前请保持单 `app` 副本**。
- 站内头像/昵称与 Steam 头像/昵称分离；Steam 页统计使用后者
- Steam 隐私过严时可能跳过本轮状态；未返回过久会超时收尾会话
- 森空岛支持扫码 / 短信 / 密码绑定，凭证加密存库；勿在 App 退出登录以免失效
- 塔吉多使用手机号验证码或密码登录老虎官方接口，凭证加密存库；用于社区 APP + 异环 / 幻塔每日签到，并完成社区每日任务（浏览/点赞/分享）与兑换
- 库街区使用手机号短信验证码绑定，凭证加密存库
- 勿提交 `.env`、`data/`、`uploads/`

- 平台数据约定：养成盒 / 旁路（含肉鸽等）存 raw（体积超阈值会打监控日志）；签到状态/奖励按「今日」写入 `*_checkin_logs`（回源后落库，调度可跳过），`bind.last_checkin_*` 仅为签到动作后的反规范化摘要。**签到页展示始终 force 回源官方**；已签才展示今日奖励；不展示执行记录。详见 [`.cursor/rules/platform-raw-cache.mdc`](.cursor/rules/platform-raw-cache.mdc)。森空岛官服/B服与补奖见 [`.cursor/rules/skland-upstream.mdc`](.cursor/rules/skland-upstream.mdc)。
- 工程：GitHub Actions 在 PR/push 上跑前端 lint+build、后端 pytest、OpenAPI drift；`main` 推送再按 `VERSION` 发 GitHub Release（含预构建 static）。API 变更后请执行 `npm run export:openapi && npm run gen:api`（见 `frontend/src/api/generated/README.md`）。
- 健康检查：`GET /health` 返回 `status` / `database` / `scheduler` / `version`；数据库不通时为 `degraded` 且 **HTTP 503**。
- 本地无 SMTP 时需设 `ALLOW_EMAIL_CODE_LOG=true` 才能用日志收验证码；`APP_ENV=production` 时启动会硬拒绝该开关。
- 应用内更新：仅管理员；默认仅 `APP_ENV=production` 允许（可用 `ALLOW_IN_APP_UPDATE` 覆盖）。更新会覆盖白名单路径，不碰 `.env` / `data/` / `uploads/` / `.venv`。