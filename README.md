# 战鸽数据 · Zhange Stats

**v0.1.18** — 签到奖励补全、用户角色管理、侧栏布局、NapCat 测试与 QQ 群名清洗。

## 功能

- 邮箱注册 / 登录（JWT）；管理员与普通用户；支持 QQ 互联登录 / 绑定
- Steam OpenID 绑定、自定义头像、Steam 日历（日时间轴 + 周/月/年热力）
- 管理端：用户 / 集成密钥（含 NapCat）/ QQ 群 / 邮箱 / 可配置定时任务 / 系统更新
- 森空岛绑定与每日自动签到（明日方舟、明日方舟：终末地）
- 明日方舟干员盒子对比（多渠道服、练度悬浮、日更缓存）；终末地盒子 raw 缓存
- 塔吉多绑定与每日自动签到（异环）
- 追放社区绑定、签到、每日任务与积分兑换
- 库街区绑定与每日自动签到（社区 + 鸣潮 / 战双）
- Docker 部署后由 **Watchtower** 自动拉取新镜像（无需管理端点更新）

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
cp .env.example .env   # 至少填 DATABASE_URL、ADMIN_*；JWT 密钥自动生成
```

邮件 SMTP、Steam/QQ 密钥、登录有效期、签到与轮询调度：登录管理员后在 **系统管理** 配置（写入 `system_configs`，无需再写进 `.env`）。

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
- 本地假监控：管理员在 **系统管理 → 定时任务** 开启（见 `backend/local_dev/README.md`）

## Docker

镜像只含应用，**MySQL 自备**。复制 `.env` 后：

```bash
docker compose pull && docker compose up -d
# 浏览器 http://<主机>:8080 （前后端同域，OAuth 回调按访问地址自动推断）
```

数据卷：`./data`（含 `.secret_key`）、`./data/uploads`（头像）。

发版：推送到 `main` 时构建一次，镜像标签为 **`VERSION` 文件版本号** + `latest`（例如 `0.1.18` 与 `latest`）。不必再推 `v*` 标签来触发构建；Watchtower 默认跟踪 `latest`。

**自动更新**：`compose.yml` 含 Watchtower，默认每 5 分钟检查 `app` 镜像；CI 推送新 `latest` 后会自动 pull 并重建。生产需先更新本机的 `compose.yml` 再 `docker compose up -d` 一次以启动 Watchtower。

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
                                         └── * endfield_box_raws
                      └── 0..1 taygedo_binds ── * taygedo_checkin_logs
                      └── 0..1 kujiequ_binds ── * kujiequ_checkin_logs
system_configs · register_challenges · job_runs · steam_apps
```

| 表 | 用途 |
|---|---|
| `users` | 账号、角色、邮箱验证 |
| `members` | 档案、站内头像/昵称、Steam 绑定（含 `steam_persona_name` / `steam_avatar_url`）、QQ 互联（`qq_openid` 等）与 `qq_number`（群成员匹配） |
| `steam_friend_edges` | 好友缓存（日历仅好友可见） |
| `play_sessions` | 游戏中会话（热力） |
| `presence_segments` | 离线/在线/游戏中（日时间轴） |
| `skland_binds` | 森空岛凭证（加密）与自动签到开关 |
| `skland_checkin_logs` | 森空岛角色签到记录 |
| `endfield_box_raws` | 终末地 card/detail 原始 JSON（按 role 最新一份） |
| `taygedo_binds` | 塔吉多凭证（加密）与自动签到开关 |
| `taygedo_checkin_logs` | 塔吉多 / 异环签到记录 |
| `kujiequ_binds` | 库街区凭证（加密）与自动签到开关 |
| `kujiequ_checkin_logs` | 库街区社区 / 鸣潮 / 战双签到记录 |
| `job_runs` | 轮询 / 签到任务日志 |
| `system_configs` | 系统配置（如 SMTP） |
| `register_challenges` | 注册验证码 |
| `steam_apps` | Steam AppID → 显示名 / 库封面图标 / 头图 / 国区价格缓存 |

启动时会 DROP 已废弃表：`games` / `match_records` / `cs2_*`。

## 说明

- 登录以邮箱为主，也支持 QQ 登录一键开号；无邮箱时可稍后完善
- 站内头像/昵称与 Steam 头像/昵称分离；Steam 页统计使用后者
- Steam 隐私过严时可能跳过本轮状态；未返回过久会超时收尾会话
- 森空岛支持扫码 / 短信 / 密码绑定，凭证加密存库；勿在 App 退出登录以免失效
- 塔吉多使用手机号验证码或密码登录老虎官方接口，凭证加密存库；用于异环 / 幻塔每日签到
- 库街区使用手机号短信验证码绑定，凭证加密存库
- 勿提交 `.env`、`data/`、`uploads/`

- 平台数据约定：养成盒存 raw；签到状态/奖励按「今日」写入 `*_checkin_logs`，打开页优先读库，无今日记录或 `force` 才查官方。详见 [`.cursor/rules/platform-raw-cache.mdc`](.cursor/rules/platform-raw-cache.mdc)。