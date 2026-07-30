# 战鸽数据 · Zhange Stats

圈子 Steam 游玩统计与成员管理。

## 功能

- **邮箱注册 / 登录**：邮箱即账号，JWT 鉴权；角色区分普通用户与管理员
- **成员档案**：注册用户与成员 1:1 同步，个人设置可改用户名、绑定 Steam ID
- **Steam 监控**：定时轮询当前游玩状态，记录会话；总览看板、成员详情、日/周/月/年日历热力
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

首次启动会自动建表、清理废弃表（`games` / `match_records`），并按 `.env` 同步管理员账号。

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
3. 「总览」查看正在游玩与近期会话；「Steam 日历」看热力统计
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
      models/               # users / members / play_sessions / job_runs / …
      schemas/
      services/             # Steam 轮询与聚合、邮件、成员同步
    alembic/                # 迁移预留（当前用 create_all + ensure_schema）
```

## 数据表（当前）

| 表 | 用途 |
|---|---|
| `users` | 账号（邮箱登录）、角色 |
| `members` | 成员档案、Steam ID |
| `play_sessions` | Steam 游玩会话 |
| `job_runs` | 轮询任务日志 |
| `system_configs` | 系统配置（如 SMTP） |
| `register_challenges` | 注册验证码 |

## 说明

- 已移除战绩录入、游戏字典、排行榜等旧能力及相关表字段
- Steam 资料隐私过严时无法获取「正在游戏」状态
- 请勿将含密钥的 `.env` 提交到仓库
