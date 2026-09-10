# 战鸽数据 · 目录结构

> 状态：**已落地**（运行时 `data/` + services/components 按域分包）  
> 目的：代码树只放代码；域文件按平台/能力分包；禁止再往 `services/`、`components/` 根上堆平台文件。

## 原则

1. **顶层不动**：`frontend/` · `backend/` · `scripts/` · `data/`。`scripts/` 内再按平台分：`linux/`（`.sh`、systemd 单元模板）、`win/`（`.ps1`）、`common/`（共用 Python）、`config.example/`（站点配置模板，按 `_version` 补键）。公开命令只有 **install / run / restart / update / backup / restore**（两边各一份）；`_lib` 不是对外入口。
2. **运行时只进 `data/`**（或安装配置里的绝对路径）。默认 `DATA_DIR=data/runtime`、`UPLOAD_DIR=data/uploads`、权重 `data/models`。相对路径相对安装根，不跟 cwd。站点管理配置在安装根 `config/`。第三方库缓存（Hugging Face / Torch / EasyOCR / pip / Playwright / tempfile）启动时 pin 到 `data/cache` 与 `data/tmp`，不要写到用户家目录。家目录里已有的战鸽权重（TexTeller hub、EasyOCR `.pth`）启动时 copy-if-missing 进安装根，不搬共享的 HF 家目录（Cursor 等）。
3. **一个域一个包**。新平台、新盒子、新日历直接进子目录，并继续套现有 Template / Chrome / Adapter。
4. **禁止一次大搬家式空 PR**。分包已完成；本文是现行布局与禁止清单，不是待办清单。
5. **不要做**：feature-sliced 重写前端；按 http/parse/db 再切 services；把 `generated/` 或 `frontend/src/data/` 当缓存挪走。

## 现行布局

```
zhange-stats/
  data/                     # 运行时（仅 README 入库）
    runtime/                # DATA_DIR：密钥、日志、SQLite、更新锁
    uploads/                # UPLOAD_DIR：avatars、articles
    models/                 # RapidOCR / EasyOCR / TexTeller
    run/ cache/ backups/ mariadb/ tmp/
  scripts/config.example/   # 站点配置模板（_version；启动/脚本补键）
  frontend/src/
    pages/                  # 路由页（攻略已在 pages/guides/）
    components/             # 根上只留跨平台外壳
      skland/ arknights/ endfield/ mihoyo/ kujiequ/ taygedo/ exilium/
      steam/ profile/ guides/tarkov/ guides/minecraft/ articles/
    api/                    # *Api.ts + generated/
    data/                   # 源码资源，不是运行时
  backend/app/
    api/                    # 已成包的保持；单文件平台 API 胀大再升包
    services/
      checkin/ skland/ mihoyo/ kujiequ/ taygedo/ exilium/ steam/ minecraft/ tarkov/ articles/ ocr/ user_files/
      （横切仍留根上，见下表）
    models/ schemas/ core/
```

`components/` 根上只留：布局/路由、`CheckinPageTemplate`、`BoxPanelChrome`、`AttendanceCalendarButton`、`ExchangePageTemplate`、`PlatformFeatureTabsPage`、`AdminHubLayout`、`AuthGuestShell`、`LegalDocView` / `LegalLinks` / `IcpBeianLink` 等跨平台外壳。

`services/` 根上只留横切：`account_anonymize`、`app_updator`、`avatar_store`、`auth_config`、`config_import`、`email*`、`file_manager`、`integrations_config`、`member_sync`、`oauth_ticket`、`password_policy`、`platform_features`、`qq_oauth`、`raw_payload_monitor`、`runtime_health`、`scheduler_*`、`security_bootstrap`、`seed`、`setup`、`site_config`、`job_runs_prune`、`game_schedule`、`box_role_cache`。OCR 进包 `ocr/`，用户附件登记进包 `user_files/`（不要叫 `files`，以免和管理端 `file_manager` 撞名）。不要在根上加 `ocr_*.py` / `user_file_*.py`。

`pages/`、平台 `api/` 单文件、`models/` 保持现状，不要求再搬家。既有 `services/adapters/`、`services/mihoyo_bbs/` 保持。

## 域包要点

### ocr/

站点共享文字识别（引擎、权重、`config/ocr.json`）。业务后处理（切块 / 闭集匹配）留在各域，例如 `tarkov/key_ocr.py`、`tarkov/raid_prep_ocr.py`。不要对外加通用识别 HTTP。

### user_files/

用户上传附件登记（`store` / `backfill`）。命名空间子目录写在 `UPLOAD_DIR`（`articles/`、`avatars/`）。头像裁剪仍走根上 `avatar_store`，落盘与登记走本包（覆盖 `avatars/{member_id}.jpg`，不另开 UUID）。启动时扫盘把存量文件补进登记表（幂等）。管理端占用与安装根增删改查仍走根上 `file_manager`，不要把用户附件元数据塞进盘点模块。

## 前端 `components/`

平台面板已在对应子目录（`skland/` · `arknights/` · `endfield/` · `mihoyo/` · `kujiequ/` · `taygedo/` · `exilium/` · `steam/` · `profile/` · `guides/*` · `articles/`）。根上不要再新增 `*BindPanel.tsx`。

| 目录 | 内容 |
|------|------|
| `skland/` | 绑定、游戏活动 |
| `arknights/` | 签到日历、盒子对比、肉鸽 |
| `endfield/` | 签到日历、养成盒 |
| `mihoyo/` | 绑定、签到日历、兑换 |
| `kujiequ/` | 绑定、签到日历、兑换、鸣潮盒子 |
| `taygedo/` | 绑定、签到日历、兑换、异星盒子 |
| `exilium/` | 绑定、兑换 |

## 新代码

- 新签到平台：`services/<platform>/client.py` + `attendance.py` + Adapter 注册；前端面板进 `components/<platform>/`，页仍套 `CheckinPageTemplate`。
- 禁止再在 `backend/app/services/` 或 `frontend/src/components/` 根上新增 `*_client.py` / `*BindPanel.tsx`。

## 生产更新

管理端「系统更新」与主机 `scripts/linux/update.sh` / `scripts/win/update.ps1` 走同一套 GitHub Release：白名单目录 **整目录删除再拷贝**（增、改、删文件，如 `backend/app`、`scripts/`）；`frontend/` **按文件同步**（新增/覆盖/删除源码，保留 `node_modules` / `dist`）；`static/` 先清空再解压 Release 预构建包。`services/` 在 `backend/app` 内，旧扁平模块名不会和分包并存。进程挂死、管理端进不去时用主机 `update`，不要 curl 管道覆盖源码。

前端生产跑的是 **CI 绿之后** GitHub Release 的 `static/` tar，打包后的 JS 已带组件路径。本机 Vite 另靠 `frontend/` 同步。发版约定见 [`deploy.md`](deploy.md)「发版」。

表结构变更走 Alembic。运行时目录（`config/` / `data/`）在保护前缀里，更新不会覆盖。首次启动会把旧 `var/` 迁进 `data/{runtime,uploads,models,…}`，并清根 `config.example/`、空壳旧目录、未使用的公式 ONNX；根 `.env` 与可能不同的 `backend/data/.secret_key` 不自动删。

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
