# 本地开发

产品介绍见根 [`README.md`](../README.md)。目录细则见 [`directory-layout.md`](directory-layout.md)。

## 技术栈

| 端 | 技术 |
|---|---|
| 前端 | React 18 · TypeScript · Vite · Ant Design 5 · TanStack Query · Zustand |
| 后端 | FastAPI · SQLAlchemy 2 · Alembic · APScheduler · MySQL · httpx · JWT / bcrypt |

## Windows 本地开发

需要 Python 3.11+、Node 18+。**不必预先安装 MySQL**：`scripts/win/install.ps1` 与 `scripts/win/run.ps1` 会在本机没有可用库时下载便携 MariaDB 11.4 到 `var/mariadb/` 并写回 `DATABASE_URL`。已有本机库（占位 `root:password` 或空密码能连上）则只建库。跳过：`$env:ZHANGE_SKIP_MARIADB=1`。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\win\install.ps1
```

```sql
-- 仅当跳过自动安装、自备库时：
CREATE DATABASE zhange_stats CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

```bash
# 仅自备库时需要：复制并填写 DATABASE_URL。走自动安装则可省略。
cp .env.example .env
```

首次打开站点会进入 **安装向导** 创建管理员。邮件 SMTP、Steam/QQ 密钥、登录有效期 / 口令策略、签到与轮询调度：登录后在侧栏 **管理** 配置（写入 `system_configs`）。本地 `APP_ENV=development` 下管理端保存不要求邮箱验证码（生产仍要）。CI 可用 `ALLOW_ENV_ADMIN_SEED=true` + `ADMIN_*` 跳过向导。

推荐用脚本（热重载；启动前会检查依赖并拉起本机 MariaDB）。脚本**不**区分生产/开发：每一份克隆是一棵独立安装树，环境只看该树 `.env`（本地通常 `APP_ENV=development`）。

```powershell
.\run.bat
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\win\run.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\win\restart.ps1
```

或手动：

```bash
# 后端
cd backend && python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
# 酒馆公式识别：主依赖已含 onnxruntime / tokenizers；权重在 var/data/texteller
# 钥匙管理 / 局前任务截图识别：rapidocr + easyocr（CPU torch）+ opencv-python-headless；权重在 var/data/rapidocr 与 var/data/easyocr。
# Linux 请用 scripts/linux/install.sh 或 run.sh（内含 CPU torch），避免 easyocr 拉 CUDA。
# 到站点设置「文字识别」从 RapidOCR 清单选档位，点「检查更新」或到任务管理跑「文字识别模型」预拉权重；识别时不再下载。
# 公式识别权重：启动会后台补齐；也可到任务配置跑「公式识别模型」。默认 hf-mirror.com
uvicorn app.main:app --reload --reload-dir app --host 127.0.0.1 --port 6130

# 前端（另开终端）
cd frontend && npm install && npm run dev
```

- API：http://127.0.0.1:6130/docs · 前端：http://127.0.0.1:6131
- 塔科夫找人线本地演示（仅 `npm run dev`）：http://127.0.0.1:6131/guides/tarkov/raid-prep/pulse-demo ；海关图上四个假人错开、随机间隔改定位，不写库、不进大厅。单人准备顶栏也有「找人线演示」入口。生产构建不挂这条路由。
- 塔科夫枪械工作台中间用 dump 枪图做底板，在图上点槽位换配件。第三方出图默认关闭。
- 启动时自动 `alembic upgrade`；改表：`alembic revision --autogenerate -m "..."`（见 [`backend/alembic/README.md`](../backend/alembic/README.md)），并同步 [`database.md`](database.md)
- 环境变量说明见 `.env.example`。Steam/QQ 回调与 CORS 默认按访问 Host 自动推断；本地 Vite 与战鸽助手（Tauri `https://tauri.localhost`）走默认正则，可用 `CORS_ORIGINS` / `CORS_ORIGIN_REGEX` 覆盖。QQ 互联后台登记的回调须与「实际打开站点的地址」一致（集成密钥页可复制）。密钥与头像目录由程序默认创建（本地安装根 `var/data/`、`var/uploads/`；相对路径相对仓库根，不跟 `backend/` cwd）。上游 HTTP 走进程级 `httpx` 连接池；可选 `REDIS_URL` 与 `DB_POOL_SIZE` 见 `.env.example`
- 平台可用性：管理员在 **管理 → 任务管理 → 任务配置** 按平台 / 游戏 / 任务级联开关
- 磁盘占用：管理员在 **管理 → 运行维护 → 文件管理** 查看运行时 / 模型 / 缓存 / 依赖占用并浏览白名单目录
- **管理端一键更新仅面向 `APP_ENV=production`（LXC）**；本机默认 `development`，不会出现该入口

Linux 本机同一套五件套：`scripts/linux/install.sh`（装系统包与 systemd 需 root）、`run.sh`、`restart.sh`、`backup.sh`、`restore.sh`。已有 systemd unit 时 `run`/`restart` 走 `systemctl`；否则起 `:6130` 后端与 `:6131` Vite。跳过装库：`ZHANGE_SKIP_MARIADB=1`。

本地假 Steam 数据见 [`backend/local_dev/README.md`](../backend/local_dev/README.md)。

## 工程

GitHub Actions 在 PR/push 上跑前端 lint+vitest+build、后端 pytest、MariaDB alembic、OpenAPI drift；`main` 推送仅在这些门绿后才按 `VERSION` 发 GitHub Release（含预构建 static），门红则不改 Release。发版约定见 [`deploy.md`](deploy.md)「发版」。API 变更后请执行 `npm run export:openapi && npm run gen:api`（见 [`frontend/src/api/generated/README.md`](../frontend/src/api/generated/README.md)）。自测分层见 [`.cursor/rules/testing.mdc`](../.cursor/rules/testing.mdc)。

改代码约定见仓库根 [`AGENTS.md`](../AGENTS.md)。Cursor 打开本仓库会加载 [`.cursor/mcp.json`](../.cursor/mcp.json)（Ant Design 5、Context7、Playwright）；无密钥，Context7 可在 MCP 面板自行加 Key。

## 目录

```
zhange-stats/
  .env.example · VERSION · scripts/linux/ · scripts/win/ · scripts/common/
  deploy/systemd/zhange-stats.service
  var/                    # 运行时（gitignore；仅 README 入库）
  frontend/               # React（src/data 为源码资源，不是运行时）
  backend/app/            # api · core · models · services/<域>
  backend/alembic/        # 迁移（表结构以 versions/ 为准）
```
