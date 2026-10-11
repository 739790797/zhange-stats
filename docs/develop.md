# 本地开发

产品介绍见根 [`README.md`](../README.md)。目录细则见 [`directory-layout.md`](directory-layout.md)。

## 技术栈

| 端 | 技术 |
|---|---|
| 前端 | React 18 · TypeScript · Vite · Ant Design 5 · TanStack Query · Zustand |
| 后端 | FastAPI · SQLAlchemy 2 · Alembic · APScheduler · MySQL · httpx · JWT / bcrypt |

## Windows 本地开发

需要 Python 3.11+、Node 22.12+（Vitest 5 / Vite 8）。**不必预先安装数据库**：`install` / `run` 只装 Python/前端依赖。首次打开站点进入 **安装向导**，可选本机 SQLite（`data/runtime/zhange.sqlite`）或填写外部 MySQL/MariaDB 连接串。本机 MariaDB 若仍需要，可手工跑 `scripts/common/provision_mariadb.py`。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\win\install.ps1
```

`install.ps1` 建 `backend\.venv`（已有 venv 低于 3.11 会让你删掉重建），先装 CPU torch 再按 `backend/constraints.txt` 装依赖，并尝试拉当前 `VERSION` 的预构建 static（校验 sha256）。拉不到只告警：开发栈 `run.ps1` 走 Vite，用不到 `static/`。之后 `run` / `restart` / 更新只在 `requirements.txt` 或 `constraints.txt` 变了时重装（见下文「Python 依赖锁」）。

```sql
-- 仅当向导选择外部 MySQL/MariaDB 时：
CREATE DATABASE zhange_stats CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

首次打开站点会进入 **安装向导**：先选库，再创建管理员；两步都要填**安装令牌**（`data/runtime/setup-token` 的内容，`run` / `restart` 会打印出来，向导完成即删除）。邮件 SMTP、Steam/QQ 密钥、登录有效期 / 口令策略、签到与轮询调度、运行环境（数据库 / Redis / `APP_ENV` / CORS）：登录后在侧栏 **管理** 配置（写入安装根 `config/*.json`）。不要再放根 `.env`。管理端保存**不再**要求邮箱验证码。无 SMTP 时：`development` 仍可把用户侧验证码打进日志；`production` 仍禁止 `ALLOW_EMAIL_CODE_LOG`。CI 用**进程环境变量** `DATABASE_URL` + `ALLOW_ENV_ADMIN_SEED=true` + `ADMIN_*` 跳过向导（不是文件）。

推荐用脚本（热重载；启动前检查 Python/前端依赖）。脚本**不**区分生产/开发、**不**自动装 MariaDB。每一份克隆是一棵独立安装树；运行环境看 `config/app.json`（或 CI 环境变量）。本地通常保持 `APP_ENV=development`。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\win\run.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\win\restart.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\win\update.ps1 -Check
```

或手动：

```bash
# 后端（Python 3.11+）
cd backend && python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
# 先装 CPU torch（不带 -c），否则 easyocr 会拉 CUDA 版
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt -c constraints.txt
pip install -r requirements-dev.txt   # pytest、ruff
# 酒馆公式识别：主依赖已含 onnxruntime / tokenizers；权重在 data/models/texteller
# 钥匙管理 / 局前任务截图识别：rapidocr + easyocr（CPU torch）+ opencv-python-headless；权重在 data/models/rapidocr 与 data/models/easyocr。
# 到站点设置「文字识别」从 RapidOCR 清单选档位，点「检查更新」或到任务管理跑「文字识别模型」预拉权重；识别时不再下载。
# 公式识别权重：启动会后台补齐；也可到任务配置跑「公式识别模型」。默认 hf-mirror.com
uvicorn app.main:app --reload --reload-dir app --host 127.0.0.1 --port 6130

# 前端（另开终端）
cd frontend && npm install && npm run dev
```

- API：http://127.0.0.1:6130/docs · 前端：http://127.0.0.1:6131
- 塔科夫找人线本地演示（仅 `npm run dev`）：http://127.0.0.1:6131/guides/tarkov/raid-prep/pulse-demo ；你看海关，甲乙在海关战局里错开换定位，丙每 30 秒在森林和海关之间换图，丁已回大厅。左上角名单带地图和状态。不写库、不进大厅。单人准备顶栏也有「找人线演示」入口。生产构建不挂这条路由。
- 塔科夫枪械工作台中间用 dump 枪图做底板，在图上点槽位换配件。第三方出图默认关闭。枪匠求解读本站 tasks dump 的 `buildWeapon`，在本站做约束满足，不打 EFTForge。
- 塔科夫 `/guides/tarkov` 不包 `PrivateRoute`：图鉴、枪匠求解、大厅预览未登录可读；个人中心与开房在壳内登录。用户等待在 **管理 → 运行维护 → 用户等待**。
- 启动时：已选库则自动 `alembic upgrade`（SQLite 首次为 `create_all` + stamp）；改表：`alembic revision --autogenerate -m "..."`（见 [`backend/alembic/README.md`](../backend/alembic/README.md)），并同步 [`database.md`](database.md)
- 战鸽助手（zhange-app）用 WebView 打开站点同源地址，首页是 `/app`（先确认登录，未登录去登录页）。嵌入侧栏、截图/日志读盘与会话边界见 [`security.md`](security.md)「战鸽助手」。Steam 日时间轴昵称链到 Steam 社区资料，不再有单独的成员游玩页。
- 站点配置字段见 [`scripts/config.example/`](../scripts/config.example/)。`install` / `run` / `restart` / `update` 与启动会按文件 `_version` 把模板里的新键补进 `config/`，不覆盖已有值。Steam/QQ 回调与 CORS 默认按访问 Host 自动推断；本地 Vite 与战鸽助手（Tauri `https://tauri.localhost`）走默认正则，可在「运行环境」覆盖 `CORS_ORIGINS` / `CORS_ORIGIN_REGEX`。QQ 互联后台登记的回调须与「实际打开站点的地址」一致（集成密钥页可复制）。密钥与头像目录由程序默认创建（本地安装根 `data/runtime/`、`data/uploads/`）。Hugging Face / Torch / EasyOCR / pip 等第三方缓存启动时 pin 到 `data/cache`，tempfile 与备份暂存在 `data/tmp`。上游 HTTP 走进程级 `httpx` 连接池；可选 `REDIS_URL` 在运行环境配置
- Linux 本机同一套六件套：`scripts/linux/install.sh`（装系统包与 systemd 需 root）、`run.sh`、`restart.sh`、`update.sh`、`backup.sh`、`restore.sh`。已有 systemd unit 时 `run`/`restart`/`update` 后的重启走 `systemctl`；否则起 `:6130` 后端与 `:6131` Vite。以 root 跑且服务用户（`ZHANGE_USER`，默认 `zhange`）存在时，venv / pip / npm / 更新器改由该用户执行，脚本退出时把安装树属主修回去；系统 Python 低于 3.11 时用 `ZHANGE_PYTHON=python3.11` 指定。本机 MariaDB 改为手工 `scripts/common/provision_mariadb.py`。
- 平台可用性：管理员在 **管理 → 任务管理 → 任务配置** 按平台 / 游戏 / 任务级联开关
- 磁盘占用：管理员在 **管理 → 运行维护 → 文件管理** 查看运行时 / 模型 / 缓存 / 依赖占用，并在安装根内增删改查（密钥、备份与 MariaDB 数据目录除外）
- **管理端一键更新仅面向 `APP_ENV=production`（LXC）**；本机默认 `development`，不会出现该入口

本地假 Steam 数据见 [`backend/local_dev/README.md`](../backend/local_dev/README.md)。

## 工程

GitHub Actions 在 PR/push 上跑前端 lint+vitest+build、后端 pytest、MariaDB 上连跑两次 `alembic upgrade head` 再 `alembic check`（模型与迁移不能漂移）与 `tests/test_mariadb_migrations.py`、OpenAPI drift；后端 job 先装 CPU torch 再按 `backend/constraints.txt` 装依赖，`pip-audit` 审计这份锁（只告警）。`main` 推送仅在这些门绿后才按 `VERSION` 发 GitHub Release（预构建 static、源码包、`SHA256SUMS`）；同名 tag 已存在就跳过、不覆盖已发资产，门红则不改 Release。发版约定见 [`deploy.md`](deploy.md)「发版」。API 变更后请执行 `npm run export:openapi && npm run gen:api`（见 [`frontend/src/api/generated/README.md`](../frontend/src/api/generated/README.md)）。自测分层见 [`.cursor/rules/testing.mdc`](../.cursor/rules/testing.mdc)。

改代码约定见仓库根 [`AGENTS.md`](../AGENTS.md)。Cursor 打开本仓库会加载 [`.cursor/mcp.json`](../.cursor/mcp.json)（Ant Design 5、Context7、Playwright；Playwright MCP 钉了版本，升级时改这里）；无密钥，Context7 可在 MCP 面板自行加 Key。

## Python 依赖锁

`backend/requirements.txt` 写直接依赖与下限；`backend/constraints.txt` 钉住解析出的全部版本。`install` / `run` / `restart` / `update` 脚本、管理端更新与 CI 都用 `-c constraints.txt` 安装。锁里**不含**：`torch` / `torchvision` 和 torch 的直接依赖（`filelock`、`fsspec`、`Jinja2`、`MarkupSafe`、`mpmath`、`networkx`、`sympy`、`typing_extensions`，跟着从 CPU 索引装好的 torch 走）、`pip` / `setuptools` / `wheel`、测试工具（`requirements-dev.txt`）。

- 何时重装：`install` 总是重装；其余入口与管理端更新比对 `backend/.venv/.zhange-req.stamp`（两份文件的 sha256，`sha256sum` 格式），一致就跳过 pip；`ZHANGE_FORCE_PIP=1` 强制重装。
- 刷新锁：在干净的 Python 3.11 与 3.12 venv 里各装一遍（先 CPU torch，再 `pip install -r requirements.txt`，不带 `-c`），合并两份 `pip freeze`，去掉上面的排除项、按包名排序写回 `constraints.txt`；两边版本不同的包（现为 numpy / scipy / tifffile，新版只支持 3.12+）按 `; python_version < "3.12"` / `>= "3.12"` 分两行钉。只有 Windows 或只有 Linux 才装的依赖（如 `colorama`、`tzdata`、`uvloop`）照旧留着，用不到的约束 pip 会忽略。
- 提交前用 [uv](https://docs.astral.sh/uv/) 只解析不安装，确认 Linux 与 Windows、3.11 与 3.12 都可解（把 `--python-version` 换成 `3.12`、`--python-platform` 换成 `x86_64-pc-windows-msvc` 各跑一遍）：

```bash
cd backend
uv pip compile requirements.txt -c constraints.txt \
  --python-version 3.11 --python-platform x86_64-unknown-linux-gnu \
  --index-url https://pypi.org/simple --extra-index-url https://download.pytorch.org/whl/cpu \
  --index-strategy unsafe-best-match --only-binary :all: > /dev/null
```

## 目录

```
zhange-stats/
  scripts/linux/ · scripts/win/ · scripts/common/ · scripts/config.example/
  scripts/linux/zhange-stats.service  # 生产 systemd 单元模板（install.sh 写入 /etc）
  data/                   # 运行时（gitignore；仅 README 入库）
  frontend/               # React（src/data 为源码资源，不是运行时）
  backend/app/            # api · core · models · services/<域>
  backend/alembic/        # 迁移（表结构以 versions/ 为准）
```
