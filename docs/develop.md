# 本地开发

产品介绍见根 [`README.md`](../README.md)。目录细则见 [`directory-layout.md`](directory-layout.md)。

## 技术栈

| 端 | 技术 |
|---|---|
| 前端 | React 18 · TypeScript · Vite · Ant Design 5 · TanStack Query · Zustand |
| 后端 | FastAPI · SQLAlchemy 2 · Alembic · APScheduler · MySQL · httpx · JWT / bcrypt |

## Windows 本地开发

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
- 塔科夫找人线本地演示（仅 `npm run dev`）：http://127.0.0.1:6131/guides/tarkov/raid-prep/pulse-demo ；海关图上两个假人每 4 秒轮流改定位，不写库、不进大厅。单人准备顶栏也有「找人线演示」入口。生产构建不挂这条路由。
- 启动时自动 `alembic upgrade`；改表：`alembic revision --autogenerate -m "..."`（见 [`backend/alembic/README.md`](../backend/alembic/README.md)），并同步 [`database.md`](database.md)
- 环境变量说明见 `.env.example`。Steam/QQ 回调与 CORS 默认按访问 Host 自动推断；本地 Vite 与战鸽助手（Tauri `https://tauri.localhost`）走默认正则，可用 `CORS_ORIGINS` / `CORS_ORIGIN_REGEX` 覆盖。QQ 互联后台登记的回调须与「实际打开站点的地址」一致（集成密钥页可复制）。密钥与头像目录由程序默认创建（本地安装根 `var/data/`、`var/uploads/`；相对路径相对仓库根，不跟 `backend/` cwd）。上游 HTTP 走进程级 `httpx` 连接池；可选 `REDIS_URL` 与 `DB_POOL_SIZE` 见 `.env.example`
- 平台可用性：管理员在 **管理 → 任务配置** 按平台 / 游戏 / 任务级联开关
- **管理端一键更新仅面向 production / LXC**；Windows 开发机默认不可用（`APP_ENV=development`）

本地假 Steam 数据见 [`backend/local_dev/README.md`](../backend/local_dev/README.md)。

## 工程

GitHub Actions 在 PR/push 上跑前端 lint+vitest+build、后端 pytest、OpenAPI drift；`main` 推送再按 `VERSION` 发 GitHub Release（含预构建 static）。API 变更后请执行 `npm run export:openapi && npm run gen:api`（见 [`frontend/src/api/generated/README.md`](../frontend/src/api/generated/README.md)）。自测分层见 [`.cursor/rules/testing.mdc`](../.cursor/rules/testing.mdc)。

改代码约定见仓库根 [`AGENTS.md`](../AGENTS.md)。

## 目录

```
zhange-stats/
  .env.example · VERSION · scripts/install.sh
  deploy/systemd/zhange-stats.service
  var/                    # 运行时（gitignore；仅 README 入库）
  frontend/               # React（src/data 为源码资源，不是运行时）
  backend/app/            # api · core · models · services/<域>
  backend/alembic/        # 迁移（表结构以 versions/ 为准）
```
