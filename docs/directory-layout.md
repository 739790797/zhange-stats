# 战鸽数据 · 目录结构

> 状态：**已落地**（运行时 `var/` + services/components 按域分包）  
> 目的：代码树只放代码；域文件按平台/能力分包；禁止再往 `services/`、`components/` 根上堆平台文件。

## 原则

1. **顶层不动**：`frontend/` · `backend/` · `scripts/` · `deploy/` · `var/`。
2. **运行时只进 `var/`**（或 `.env` 绝对路径）。相对 `DATA_DIR` / `UPLOAD_DIR` 相对安装根，不跟 cwd。
3. **一个域一个包**。新平台、新盒子、新日历直接进子目录，并继续套现有 Template / Chrome / Adapter。
4. **禁止一次大搬家式空 PR**。本文件给出目标布局；实施按下方步骤，每步可测。
5. **不要做**：feature-sliced 重写前端；按 http/parse/db 再切 services；把 `generated/` 或 `frontend/src/data/` 当缓存挪走。

## 目标布局

```
zhange-stats/
  var/                      # 运行时（仅 README 入库）
  frontend/src/
    pages/                  # 路由页（攻略已在 pages/guides/）
    components/             # 根上只留跨平台外壳
      skland/ arknights/ endfield/ mihoyo/ kujiequ/ taygedo/ exilium/
      steam/ profile/ guides/tarkov/ guides/minecraft/
    api/                    # *Api.ts + generated/
    data/                   # 源码资源，不是运行时
  backend/app/
    api/                    # 已成包的保持；单文件平台 API 胀大再升包
    services/
      checkin/ skland/ mihoyo/ kujiequ/ taygedo/ exilium/ steam/ minecraft/ tarkov/
      （横切仍留根上，见下表）
    models/ schemas/ core/
```

`components/` 根上只留：布局/路由、`CheckinPageTemplate`、`BoxPanelChrome`、`AttendanceCalendarButton`、`ExchangePageTemplate`、`PlatformFeatureTabsPage`、`AuthGuestShell`、`LegalDocView` / `LegalLinks` / `IcpBeianLink` 等跨平台外壳。

`services/` 根上只留横切：`app_updator`、`avatar_store`、`auth_config`、`email*`、`integrations_config`、`member_sync`、`oauth_ticket`、`password_policy`、`platform_features`、`qq_oauth`、`raw_payload_monitor`、`runtime_health`、`scheduler_*`、`security_bootstrap`、`seed`、`setup`、`job_runs_prune`、`game_schedule`、`box_role_cache`。

## 后端 `services/` 映射

旧模块名 `app.services.<旧>` → `app.services.<包>.<新>`。

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

### mihoyo/ · kujiequ/ · taygedo/ · exilium/

去掉平台前缀：`mihoyo_client.py` → `mihoyo.client`，`*_attendance` → `attendance`，`*_checkin` → `checkin`，以及 `auth` / `calendar` / `qr` / `boxes`（有则收）。

### steam/ · tarkov/

去掉前缀：`steam_bind.py` → `steam.bind`，`tarkov_items.py` → `tarkov.items`，其余同理。

### minecraft/

去掉 `minecraft_` 前缀。`pelican_client.py` → `minecraft.pelican`。

## 前端 `components/` 映射

文件名不变，只换目录。已在子目录的（`arknights/` 内实现、`steam/`、`profile/`、`guides/*`）不重复搬。

| 现文件 | 目标 |
|--------|------|
| `SklandBindPanel.tsx` · `SklandGameEventsPanel.tsx` | `skland/` |
| `ArknightsAttendanceCalendar.tsx` | `arknights/` |
| `ArknightsBoxCompare.tsx`（若仅为 re-export） | 删除，改为从 `arknights/` 引用 |
| `EndfieldAttendanceCalendar.tsx` · `EndfieldBoxPanel.tsx` | `endfield/` |
| `MihoyoBindPanel.tsx` · `MihoyoAttendanceCalendar.tsx` · `MihoyoExchangePanel.tsx` | `mihoyo/` |
| `KujiequBindPanel.tsx` · `KujiequAttendanceCalendar.tsx` · `KujiequExchangePanel.tsx` · `WwBoxPanel.tsx` | `kujiequ/` |
| `TaygedoBindPanel.tsx` · `TaygedoAttendanceCalendar.tsx` · `TaygedoExchangePanel.tsx` · `ExastrisBoxPanel.tsx` | `taygedo/` |
| `ExiliumBindPanel.tsx` · `ExiliumExchangePanel.tsx` | `exilium/` |

`pages/`、`api/` 单文件、`models/` **本轮不搬**。

## 实施步骤

每步结束后应能 `python -m pytest -q`（后端步）或 `npm run test`（前端步）。

| 步 | 做什么 | 完成标准 |
|----|--------|----------|
| 0 | 运行时进 `var/` | 已完成（`app.core.paths`） |
| 1 | 落本文档；`AGENTS.md` 与架构索引引用 | 已完成 |
| 2–3 | 后端 `services/` 进包并改为新 import（未留 shim） | 已完成 |
| 4 | 前端平台组件进子目录；改 `@/components/...` | 已完成 |
| 5 | 同步 `frontend-conventions` / `backend-conventions` | 已完成 |
| 6 | pytest + vitest | 已完成（402 / 149） |

未搬：`pages/`、平台 `api/` 单文件、`models/`；既有 `services/adapters/`、`services/mihoyo_bbs/` 保持。

## 生产更新

管理端「系统更新」和 `scripts/emergency_update.sh` 都对白名单目录做 **整目录删除再拷贝**（`backend/app`、`deploy/` 等）。这次 `services/` 搬家落在 `backend/app` 内，旧的 `skland_checkin.py` 会随整树清掉，不会和 `skland/checkin.py` 并存。

前端源码不在源码白名单里。生产跑的是 Release 的 `static/` tar（同样先清空再解压），打包后的 JS 已带新组件路径，不依赖 LXC 上残留的 `frontend/src`。

services 搬家本身不需要 Alembic。同发版若含表结构变更（如去掉 `members.qq_number` / NapCat 配置），走正常迁移。运行时目录（`data/` / `uploads/` / `var/` / `.env`）在保护前缀里，更新不会覆盖。已有 LXC 若 `.env` 或 systemd 仍指向安装根 `data/`，继续用即可。

## 新代码（收口后）

- 新签到平台：`services/<platform>/client.py` + `attendance.py` + Adapter 注册；前端面板进 `components/<platform>/`，页仍套 `CheckinPageTemplate`。
- 禁止再在 `backend/app/services/` 或 `frontend/src/components/` 根上新增 `*_client.py` / `*BindPanel.tsx`。
