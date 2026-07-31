# 战鸽数据 · Zhange Stats

**v0.1.6** — 圈子 Steam 游玩统计：今天谁在玩、好友日历、个人资料与 Steam 绑定。

## 功能

- 邮箱注册 / 登录（JWT）；管理员与普通用户
- Steam OpenID 绑定、自定义头像、今天玩什么（日时间轴 + 周/月/年热力）
- 圈子内 Steam 好友；管理端：用户 / SMTP
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
cp .env.example .env   # 至少填 DATABASE_URL、ADMIN_*；SECRET_KEY 可留空自动生成
```

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
- 环境变量说明见 `.env.example`（`DATA_DIR` 存密钥，`UPLOAD_DIR` 存头像；CORS 勿写 `*`）

## Docker

镜像只含应用，**MySQL 自备**。复制 `.env` 后：

```bash
docker compose pull && docker compose up -d
# 浏览器 http://<主机>:8080
```

数据卷：`./data`（含 `.secret_key`）、`./data/uploads`（头像）。

发版：推送到 `main` 时构建一次，镜像标签为 **`VERSION` 文件版本号** + `latest`（例如 `0.1.6` 与 `latest`）。不必再推 `v*` 标签来触发构建；Watchtower 默认跟踪 `latest`。

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
system_configs · register_challenges · job_runs
```

| 表 | 用途 |
|---|---|
| `users` | 账号、角色、邮箱验证 |
| `members` | 档案、Steam 绑定（与用户 1:1） |
| `steam_friend_edges` | 好友缓存（日历仅好友可见） |
| `play_sessions` | 游戏中会话（热力） |
| `presence_segments` | 离线/在线/游戏中（日时间轴） |
| `job_runs` | 轮询任务日志 |
| `system_configs` | 系统配置（如 SMTP） |
| `register_challenges` | 注册验证码 |

启动时会 DROP 已废弃表：`games` / `match_records` / `cs2_*`。

## 说明

- 登录以邮箱为主；`username` 用于 JWT 与种子管理员
- Steam 隐私过严时可能跳过本轮状态；未返回过久会超时收尾会话
- 勿提交 `.env`、`data/`、`uploads/`
