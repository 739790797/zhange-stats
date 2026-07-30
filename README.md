# 圈子战绩 · CircleStats

朋友小圈子的战绩归档与排行统计（MVP）。

## 功能（第一期）

- 账号登录（JWT，无公开注册）
- 圈子成员管理
- 游戏字典
- 手动录入战绩
- 总览看板、排行榜、个人主页

## 技术栈

| 端 | 技术 |
|---|---|
| 前端 | React 18 + TypeScript + Vite + Ant Design 5 + TanStack Query + Zustand |
| 后端 | FastAPI + SQLAlchemy 2 + MySQL + JWT/bcrypt |

## 环境准备

1. Python 3.11+
2. Node.js 18+
3. MySQL 8.x，并创建数据库：

```sql
CREATE DATABASE circlestats CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

4. 复制环境变量：

```bash
cp .env.example .env
```

按需修改 `DATABASE_URL`、`SECRET_KEY` 等。后端也会读取项目根目录的 `.env`。

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

首次启动会自动建表，并种子：

- 管理员账号：`admin` / `admin123`（生产环境务必修改）
- 示例游戏：王者荣耀、CS2

接口文档：http://127.0.0.1:8000/docs

## 启动前端

```bash
cd frontend
npm install
npm run dev
```

浏览器打开：http://127.0.0.1:5173  

开发模式下 Vite 会把 `/api` 代理到 `http://127.0.0.1:8000`。

## 推荐验收路径

1. 使用 `admin` / `admin123` 登录，进入总览
2. 「系统设置」→ 新增成员
3. 「战绩录入」→ 选择成员/游戏，提交一条战绩
4. 回到总览与排行榜，确认数据变化

## 目录结构

```
zhange-stats/
  .env.example
  README.md
  frontend/          # React 中后台
  backend/
    app/
      api/           # 路由
      core/          # 配置、数据库、鉴权
      models/
      schemas/
      services/      # 统计聚合；adapters/ 预留各游戏数据源
    alembic/         # 迁移目录预留（MVP 使用 create_all）
```

## 下一步（第二期）

- Steam / 各游戏官方或社区数据 adapter（见 `backend/app/services/adapters/`）
- 系统 cron 调用 FastAPI 任务接口做定时同步
- 成就徽章、趣味称号
- Alembic 正式迁移与邀请码入圈

## 明确不做（第一期）

- 真实游戏爬虫 / 自动化抓取
- 公开注册
- Redis / Celery
- 复杂权限矩阵
