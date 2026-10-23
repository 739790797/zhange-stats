# 战鸽数据 · 目录结构

> 状态：**已落地**（前端 feature-first、运行时 `data/` 与后端 services 按域分包）
> 目的：代码树只放代码；业务按平台/能力归属；禁止再往后端 `services/` 根上堆平台文件。

## 原则

1. **顶层不动**：`frontend/` · `backend/` · `scripts/` · `data/`。`scripts/` 内再按平台分：`linux/`（`.sh`、systemd 单元模板）、`win/`（`.ps1`）、`common/`（共用 Python）、`config.example/`（站点配置模板，按 `_version` 补键）。公开命令只有 **install / run / restart / update / backup / restore**（两边各一份）；`_lib` 不是对外入口。
2. **运行时只进 `data/`**（或安装配置里的绝对路径）。默认 `DATA_DIR=data/runtime`、`UPLOAD_DIR=data/uploads`、权重 `data/models`。相对路径相对安装根，不跟 cwd。站点管理配置在安装根 `config/`。第三方库缓存（Hugging Face / pip / Playwright / tempfile）启动时 pin 到 `data/cache` 与 `data/tmp`，不要写到用户家目录。家目录里已有的战鸽权重（TexTeller hub）启动时 copy-if-missing 进安装根，不搬共享的 HF 家目录（Cursor 等）。
3. **一个域一个包**。新平台、新盒子、新日历直接进子目录，并继续套现有 Template / Chrome / Adapter。
4. **禁止一次大搬家式空 PR**。分包已完成；本文是现行布局与禁止清单，不是待办清单。
5. **不要做**：按 http/parse/db 再切 services；把前端 `shared/api/generated/` 契约或 `features/*/data/` 源码资源当运行时数据迁进根 `data/`。

## 现行布局

```
zhange-stats/
  data/                     # 运行时（仅 README 入库）
    runtime/                # DATA_DIR：密钥、日志、SQLite、更新锁
    uploads/                # UPLOAD_DIR：avatars、articles
    models/                 # TexTeller（公式识别）
    repos/ run/ cache/ backups/ mariadb/ tmp/
  scripts/config.example/   # 站点配置模板（_version；启动/脚本补键）
  frontend/src/
    app/                    # 启动、路由组合、全局壳与应用级样式
    features/               # 按业务所有权分组；platforms/ 与 guides/ 再按域分包
    shared/                 # 通用 UI、HTTP 基础设施、工具与生成契约
  backend/app/
    api/ cli/                # API；cli/ 提供 python -m app.cli run-job
    services/
      checkin/ skland/ (endfield_inn/) mihoyo/ kujiequ/ taygedo/ exilium/ steam/ minecraft/ tarkov/ ror2/ guide_raw/ articles/ user_files/
      （横切仍留根上，见下表）
    models/ schemas/ core/
```

`services/` 根上只留横切：`account_anonymize`、`app_updator`、`avatar_store`、`auth_config`、`config_import`、`email*`、`file_manager`、`integrations_config`、`member_sync`、`oauth_ticket`、`password_policy`、`platform_features`、`qq_oauth`、`raw_payload_monitor`、`runtime_health`、`rum`、`scheduler_*`、`security_bootstrap`、`seed`、`setup`、`site_config`、`job_run_*`、`job_runner`、`job_execution_lock`、`job_process_supervisor`、`job_runs_prune`、`game_schedule`、`box_role_cache`。同步任务的手动 CLI 入口在 `backend/app/cli/`，运行器与锁仍由 `services/` 共用。用户附件登记进包 `user_files/`（不要叫 `files`，以免和管理端 `file_manager` 撞名）。不要在根上加 `user_file_*.py`。

`backend/app/api/`、`models/` 与 `services/adapters/`、`services/mihoyo_bbs/` 保持现有职责；前端页面、业务 API 与模型按 feature owner 归档。

## 域包要点

### user_files/

用户上传附件登记（`store` / `backfill`）。命名空间子目录写在 `UPLOAD_DIR`（`articles/`、`avatars/`）。头像裁剪仍走根上 `avatar_store`，落盘与登记走本包（覆盖 `avatars/{member_id}.jpg`，不另开 UUID）。启动时扫盘把存量文件补进登记表（幂等）。管理端占用与安装根增删改查仍走根上 `file_manager`，不要把用户附件元数据塞进盘点模块。

## 前端源码目录

前端源码统一按 `app/`、`features/`、`shared/` 组织；业务所有权、跨 feature 复用、API/types 与样式资源的归属规则见 [前端架构约定](frontend-architecture.md)。不要再在旧的根级 `frontend/src/pages/`、`components/`、`lib/` 或业务 `api/` 中新增代码。

平台业务组件归 `frontend/src/features/platforms/<platform>/`，攻略归 `frontend/src/features/guides/<guide>/`；域内复用放各自 `shared/`。通用 UI、hooks、纯工具和设计 token 放 `frontend/src/shared/`，应用启动/路由/全局壳放 `frontend/src/app/`。

## 新代码

- 新签到平台：后端进入 `services/<platform>/client.py` + `attendance.py` + Adapter 注册；前端归 `features/platforms/<platform>/`，页面仍套 `CheckinPageTemplate`。
- 禁止再在 `backend/app/services/` 中新增扁平 `*_client.py`；前端不得恢复旧的根级业务组件目录。

## 生产更新

管理端「系统更新」与主机 `scripts/linux/update.sh` / `scripts/win/update.ps1` 走同一套 GitHub Release：白名单目录 **整目录删除再拷贝**（增、改、删文件，如 `backend/app`、`scripts/`）；`frontend/` **按文件同步**（新增/覆盖/删除源码，保留 `node_modules` / `dist`）；`static/` 先清空再解压 Release 预构建包。`services/` 在 `backend/app` 内，旧扁平模块名不会和分包并存。进程挂死、管理端进不去时用主机 `update`，不要 curl 管道覆盖源码。

前端生产跑的是 **CI 绿之后** GitHub Release 的 `static/` tar，打包后的 JS 已带组件路径。本机 Vite 另靠 `frontend/` 同步。发版约定见 [`deploy.md`](deploy.md)「发版」。

表结构变更走 Alembic。运行时目录（`config/` / `data/`）在保护前缀里，更新不会覆盖。首次启动会把旧 `var/` 迁进 `data/{runtime,uploads,models,…}`，并清根 `config.example/`、空壳旧目录、未使用的公式 ONNX；根 `.env` 与可能不同的 `backend/data/.secret_key` 不自动删。

## 上游数据仓

`backend/app/services/upstream_repos.py` 将 EndfieldData、ArknightsGameResource、Tarkov overlay 与 Tarkov SVG 浅克隆到安装根 `data/repos/`。任务管理在对应游戏下分别展示「外部仓库更新」，每天 03:50 更新默认分支，早于方舟投影 04:00 和塔科夫全量同步 04:25；任务旁的 GitHub 图标打开对应仓库。每个仓库同步任务默认 30 分钟超时，可在任务配置页单独调整（1–1440 分钟）；超时会终止当前 Git 命令。同步锁按仓库隔离，某仓同步不会阻塞其他仓库的读取。缺仓时读请求返回统一提示，前端引导到任务配置手动触发同步。更新失败保留旧工作树。`data/repos/` 由 Git 忽略且备份排除，但仍属于文件管理器可浏览和管理的普通目录。服务端只读注册的仓库 ID 和仓库内相对路径。

## 附录：历史搬家对照（已完成）

旧模块名 `app.services.<旧>` → 现行 `app.services.<包>.<新>`。不要按此表再开搬家 PR。

### checkin/

| 旧文件 | 新模块 |
|--------|--------|
| `checkin_adapter.py` | `checkin.adapter` |
| `checkin_common.py` | `checkin.common` |
| `checkin_orchestrator.py` | `checkin.orchestrator` |
| `checkin_registry.py` | `checkin.registry` |
| `checkin_role_prefs.py` | `checkin.role_prefs` |
| `checkin_schedule.py` | `checkin.schedule` |

### skland/

| 旧文件 | 新模块 |
|--------|--------|
| `skland_client.py` | `skland.client` |
| `skland_attendance.py` | `skland.attendance` |
| `skland_checkin.py` | `skland.checkin` |
| `skland_boxes.py` | `skland.boxes` |
| `skland_calendar.py` | `skland.calendar` |
| `skland_qr.py` | `skland.qr` |
| `skland_awards.py` | `skland.awards` |
| `skland_rogue.py` | `skland.rogue` |
| `skland_session_cache.py` | `skland.session_cache` |
| `endfield_calendar.py` | `skland.endfield_calendar` |
| `arknights_box_compare.py` | `skland.arknights_box_compare` |
| `arknights_catalog.py` | `skland.arknights_catalog` |

### 其它域

去掉平台前缀：`mihoyo_client.py` → `mihoyo.client`，`*_attendance` → `attendance`，`*_checkin` → `checkin`，以及 `auth` / `calendar` / `qr` / `boxes`（有则收）。`steam_bind.py` → `steam.bind`，`tarkov_items.py` → `tarkov.items`。Minecraft 去掉 `minecraft_` 前缀；`pelican_client.py` → `minecraft.pelican`。
