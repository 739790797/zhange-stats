# 战鸽数据 · Zhange Stats

圈子 Steam 游玩统计与成员管理。

## 功能

- **邮箱注册 / 登录**：邮箱即账号，JWT 鉴权；角色区分普通用户与管理员
- **成员档案**：注册用户与成员 1:1 同步，个人设置可改用户名、绑定 Steam ID
- **Steam 监控**：定时轮询在线 / 离线 / 游戏中状态；总览、成员详情、日时间轴与周/月/年热力
- **系统设置**（管理员）：用户管理（角色 / 删除）、SMTP 邮箱配置

## 技术栈

| 端 | 技术 |
|---|---|
| 前端 | React 18 · TypeScript · Vite · Ant Design 5 · TanStack Query · Zustand |
| 后端 | FastAPI · SQLAlchemy 2 · APScheduler · MySQL/MariaDB · JWT / bcrypt |

## 环境准备

1. Python 3.11+
2. Node.js 18+
3. MySQL / MariaDB，创建库：

```sql
CREATE DATABASE zhange_stats CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

4. 复制环境变量并填写：

```bash
cp .env.example .env
```

必填：`DATABASE_URL`、`SECRET_KEY`、`ADMIN_*`。Steam 轮询需 `STEAM_API_KEY`。邮件验证码可配 SMTP，未配置时验证码会打印到后端控制台。

## 启动后端

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

首次启动会自动建表（`create_all`）、执行 `ensure_schema`（补列 / 删除废弃表），并按 `.env` 同步管理员账号。

接口文档：http://127.0.0.1:8000/docs

## 启动前端

```bash
cd frontend
npm install
npm run dev
```

浏览器打开：http://127.0.0.1:5173  

开发模式下 Vite 将 `/api` 代理到 `http://127.0.0.1:8000`。

## 推荐体验路径

1. 用邮箱注册并登录，或使用 `.env` 中的管理员账号
2. 「个人设置」绑定 Steam ID（资料需对好友 / 公开可见）
3. 「总览」查看正在游玩与近期会话；「Steam 日历」默认日时间轴，亦可切换周/月/年热力
4. 管理员：「系统设置」→ 用户管理 / 邮箱设置

## 目录结构

```
zhange-stats/
  .env.example
  README.md
  frontend/                 # React 中后台
  backend/
    app/
      api/                  # 路由：auth / members / profile / steam / settings
      core/                 # 配置、数据库、鉴权、schema 补丁
      models/               # ORM 模型（与下方「数据库表结构」一一对应）
      schemas/
      services/             # Steam 轮询与聚合、邮件、成员同步
    alembic/                # 迁移预留（当前用 create_all + ensure_schema）
```

## 数据库表结构

> **维护约定：只要新增 / 删除表，或增删改字段、索引、约束，必须同步更新本节，并在同一次改动中提交 README。**  
> 源码以 `backend/app/models/` 为准；启动时由 `create_all` + `ensure_schema` 对齐库结构。字符集建议 `utf8mb4`。

### ER 关系（简图）

```
users 1 ── 1 members
              │
              ├── * play_sessions
              └── * presence_segments

system_configs          （独立 KV）
register_challenges     （独立，按邮箱）
job_runs                （独立任务日志）
```

### 总览

| 表名 | 模型文件 | 用途 |
|---|---|---|
| `users` | `models/user.py` | 登录账号、角色、邮箱验证 |
| `members` | `models/member.py` | 成员档案、Steam ID，与用户 1:1 |
| `play_sessions` | `models/play_session.py` | 游戏中会话（周/月/年热力、总览游玩时长） |
| `presence_segments` | `models/presence_segment.py` | 离线/在线/游戏中片段（日时间轴） |
| `job_runs` | `models/job_run.py` | Steam 轮询等任务执行日志 |
| `system_configs` | `models/system_config.py` | 系统配置（如 SMTP JSON） |
| `register_challenges` | `models/register_challenge.py` | 注册邮箱验证码挑战 |

---

### `users`

| 列名 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | `INT` | PK, AI | 主键 |
| `username` | `VARCHAR(64)` | UNIQUE, NOT NULL, INDEX | 内部用户名（注册自动生成；管理员种子用 `ADMIN_USERNAME`）；JWT subject |
| `email` | `VARCHAR(128)` | UNIQUE, NULL, INDEX | 登录邮箱（业务上即账号） |
| `display_name` | `VARCHAR(64)` | NOT NULL | 展示名 / 用户名 |
| `password_hash` | `VARCHAR(255)` | NOT NULL | bcrypt 哈希 |
| `is_admin` | `TINYINT(1)` / `BOOLEAN` | NOT NULL, DEFAULT 0 | 与 `role` 双写，兼容旧库 |
| `role` | `ENUM('user','admin')` | NOT NULL, DEFAULT `'user'` | 角色 |
| `email_verified` | `TINYINT(1)` / `BOOLEAN` | NOT NULL, DEFAULT 0 | 是否已验证邮箱 |
| `verify_code` | `VARCHAR(16)` | NULL | 遗留验证码字段（注册主流程用 `register_challenges`） |
| `verify_code_expires_at` | `DATETIME(6)` TZ | NULL | 遗留验证码过期时间 |
| `created_at` | `DATETIME(6)` TZ | NOT NULL, DEFAULT now | 创建时间 |

关系：`users.id` ← `members.user_id`（一对一）。

---

### `members`

| 列名 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | `INT` | PK, AI | 主键 |
| `nickname` | `VARCHAR(64)` | NOT NULL, INDEX | 昵称（与对应用户 `display_name` 同步） |
| `avatar_url` | `VARCHAR(512)` | NULL | 头像 URL |
| `steam_id` | `VARCHAR(32)` | UNIQUE, NULL, INDEX | 64 位 SteamID |
| `user_id` | `INT` | UNIQUE, NULL, FK → `users.id` | 绑定用户；业务上仅展示已绑定用户的成员 |
| `joined_at` | `DATETIME(6)` TZ | NOT NULL, DEFAULT now | 加入时间 |

关系：一对多 `play_sessions`、`presence_segments`。

---

### `play_sessions`

仅在 **游戏中** 时由轮询开/续/关，供热力与时长统计。

| 列名 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | `INT` | PK, AI | 主键 |
| `member_id` | `INT` | NOT NULL, INDEX, FK → `members.id` | 成员 |
| `steam_app_id` | `VARCHAR(32)` | NOT NULL, INDEX | Steam AppID |
| `game_name` | `VARCHAR(128)` | NOT NULL | 游戏名（`gameextrainfo`） |
| `started_at` | `DATETIME(6)` TZ | NOT NULL, INDEX | 会话开始 |
| `last_seen_at` | `DATETIME(6)` TZ | NOT NULL | 最近一次仍在玩的探测时间 |
| `ended_at` | `DATETIME(6)` TZ | NULL, INDEX | 结束时间；`NULL` 表示进行中 |
| `source` | `VARCHAR(32)` | NOT NULL, DEFAULT `'steam'` | 数据来源 |

---

### `presence_segments`

轮询写入的完整状态轴：`offline` / `online` / `playing`，供 **日视图时间轴**。

| 列名 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | `INT` | PK, AI | 主键 |
| `member_id` | `INT` | NOT NULL, INDEX, FK → `members.id` | 成员 |
| `status` | `VARCHAR(16)` | NOT NULL, INDEX | `offline` \| `online` \| `playing` |
| `steam_app_id` | `VARCHAR(32)` | NULL, INDEX | `playing` 时的 AppID |
| `game_name` | `VARCHAR(128)` | NULL | `playing` 时的游戏名 |
| `started_at` | `DATETIME(6)` TZ | NOT NULL, INDEX | 片段开始 |
| `last_seen_at` | `DATETIME(6)` TZ | NOT NULL | 最近一次状态仍成立的探测时间 |
| `ended_at` | `DATETIME(6)` TZ | NULL, INDEX | 结束；`NULL` 表示当前片段仍进行中 |
| `source` | `VARCHAR(32)` | NOT NULL, DEFAULT `'steam'` | 数据来源 |

状态判定（Steam `GetPlayerSummaries`）：有 `gameid` → `playing`；`personastate = 0` 或缺失 → `offline`；其余 → `online`。

---

### `job_runs`

| 列名 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `id` | `INT` | PK, AI | 主键 |
| `job_key` | `VARCHAR(64)` | NOT NULL, INDEX | 任务键，如 `steam_presence` |
| `started_at` | `DATETIME(6)` TZ | NOT NULL, DEFAULT now | 开始 |
| `finished_at` | `DATETIME(6)` TZ | NULL | 结束 |
| `status` | `VARCHAR(32)` | NOT NULL, DEFAULT `'running'` | `running` / `ok` / `error` 等 |
| `message` | `TEXT` | NULL | 摘要或错误信息 |
| `stats` | `JSON` | NULL | 计数等结构化结果 |

---

### `system_configs`

| 列名 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `key` | `VARCHAR(64)` | PK | 配置键，如邮箱 SMTP |
| `value` | `TEXT` | NOT NULL, DEFAULT `'{}'` | 一般为 JSON 字符串 |

---

### `register_challenges`

| 列名 | 类型 | 约束 | 说明 |
|---|---|---|---|
| `email` | `VARCHAR(128)` | PK | 待注册邮箱 |
| `code` | `VARCHAR(16)` | NOT NULL | 验证码 |
| `expires_at` | `DATETIME(6)` TZ | NOT NULL | 过期时间 |

---

### 已废弃（启动时 DROP）

| 表名 | 说明 |
|---|---|
| `games` | 旧游戏字典 |
| `match_records` | 旧战绩记录 |

`members.extra_bindings` 字段亦已废弃，`ensure_schema` 会尝试删除该列。

## 说明

- 登录以邮箱为主；`username` 仍用于 JWT 与管理员种子账号
- Steam 资料隐私过严时可能无法获取「正在游戏」；未返回的玩家本轮轮询会跳过
- 请勿将含密钥的 `.env` 提交到仓库
