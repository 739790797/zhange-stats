# 数据库表结构

改表须新增 Alembic 迁移，并更新本文总览。细节以 `models/` + `alembic/versions/` 为准。迁移流程见 [`backend/alembic/README.md`](../backend/alembic/README.md)。

```
users 1 ── 1 members ── * play_sessions / presence_segments
                      └── 0..1 skland_binds ── * skland_checkin_logs
                                         └── * skland_attendance_raws
                                         └── * endfield_box_raws
                                         └── * arknights_box_snapshots
                                         └── * arknights_rogue_raws
                      └── 0..1 taygedo_binds ── * taygedo_checkin_logs
                                         └── * taygedo_attendance_raws
                                         └── * exastris_box_raws
                      └── 0..1 exilium_binds ── * exilium_checkin_logs
                      └── 0..1 kujiequ_binds ── * kujiequ_checkin_logs
                                         └── * kujiequ_attendance_raws
                                         └── * kujiequ_ww_box_raws
                      └── 0..1 mihoyo_binds ── * mihoyo_checkin_logs
                                         └── * mihoyo_attendance_raws
                      └── * checkin_role_prefs（按平台/角色加入本站 + 自动签到）
system_configs · register_challenges · oauth_exchange_tickets · job_runs · steam_apps
arknights_operators · arknights_catalog_meta · game_schedule_raws
tarkov_items_raws · tarkov_items_meta
tarkov_ammo · tarkov_ammo_meta
tarkov_guns · tarkov_gun_meta
tarkov_tasks_raws · tarkov_tasks_meta
tarkov_traders_raws · tarkov_traders_meta
tarkov_bosses_raws · tarkov_bosses_meta
tarkov_guides_raws · tarkov_guides_meta
tarkov_tracker_binds
tarkov_raid_rooms ── * tarkov_raid_room_members / tarkov_raid_room_task_claims / tarkov_raid_room_marks
minecraft_server_profiles · minecraft_perf_samples · minecraft_perf_rollups · minecraft_presence_segments
```

| 表 | 用途 |
|---|---|
| `users` | 账号、`role`（权限唯一来源）、邮箱验证；API 仍返回派生字段 `is_admin` |
| `members` | 档案、站内头像/昵称、Steam 绑定（含 `steam_persona_name` / `steam_avatar_url`）、QQ 互联（`qq_openid` 等）；`user_id` ON DELETE CASCADE |
| `play_sessions` | 游戏中会话（热力）；索引含 `(member_id, started_at)` / `(member_id, ended_at)` / `(source, started_at)` / `last_seen_at`（复合最左前缀覆盖 member_id，无单列 member_id）；`member_id` ON DELETE CASCADE |
| `presence_segments` | 离线/在线/游戏中（日时间轴）；索引含 `(member_id, started_at)` / `(member_id, ended_at)`；`member_id` ON DELETE CASCADE |
| `skland_binds` | 森空岛凭证（加密）；`auto_checkin` 为各角色偏好派生摘要；`checkin_hour` / `checkin_minute` 仅作旧数据种子（调度与上次执行以 prefs / logs 为准） |
| `checkin_role_prefs` | 各平台按角色的「加入本站」(`included`) 与自动签到开关/北京时间（`platform`+`game_code`+`role_uid`）；签到页与调度仅处理 `included`；`enabled` 另控自动签到；调度索引 `(platform, enabled, checkin_hour, checkin_minute)` |
| `skland_checkin_logs` | 森空岛角色签到记录（展示路径打开页始终回源后 upsert；`source`=`status` 查询 / `action` 真正执行，不驱动产品 UI；含 `awards_text` / `awards_json`；调度可按今日成功态跳过；超期由 `job_runs_prune` 清理） |
| `skland_attendance_raws` | 明日方舟签到日历 GET attendance 原始 JSON（按 member+uid 最新一份；跨月或 force / 签到后回源） |
| `game_schedule_raws` | 活动日历上游原始 JSON（按游戏 `arknights` / `endfield` 各一份；读库优先；定时 / force 回源；失败不覆盖） |
| `endfield_box_raws` | 终末地 card/detail 原始 JSON（按 role 最新一份） |
| `endfield_attendance_raws` | 终末地签到日历 GET attendance 原始 JSON（按 member+role 最新一份；跨月或 force / 签到后回源） |
| `arknights_operators` | 明日方舟干员图鉴（自开源 character_table 同步） |
| `arknights_catalog_meta` | 图鉴同步元数据（单行，含版本与同步时间） |
| `tarkov_items_raws` | 逃离塔科夫物品上游原始 JSON（id=1 PVP / id=2 PVE；GraphQL split 或 json.tarkov.dev items；弹药/枪械共用；失败不覆盖） |
| `tarkov_items_meta` | 物品同步元数据（id 与 raw 对应，含 ammo/gun 计数与同步时间） |
| `tarkov_ammo` | 弹药派生读模型（items raw parse；含 `ammo_type` / `icon_link` / 初速 / 精度·后坐·流血修正；供列表/散点） |
| `tarkov_ammo_meta` | 弹药展示元数据（单行；与 items 同事务写入） |
| `tarkov_guns` | 枪械派生读模型（口径/射速/人机/后坐/`allowed_ammo` 等） |
| `tarkov_gun_meta` | 枪械展示元数据（单行） |
| `tarkov_tasks_raws` | 逃离塔科夫任务上游原始 JSON（id=1 PVP / id=2 PVE；GraphQL 或 json.tarkov.dev tasks + locale；失败不覆盖） |
| `tarkov_tasks_meta` | 任务同步元数据（id 与 raw 对应，含 task_count 与同步时间） |
| `tarkov_traders_raws` | 逃离塔科夫商人上游原始 JSON（id=1 PVP / id=2 PVE；json.tarkov.dev traders + locale + 物品 buyFromTrader 报价；失败不覆盖） |
| `tarkov_traders_meta` | 商人同步元数据（id 与 raw 对应，含 trader_count / offer_count 与同步时间） |
| `tarkov_bosses_raws` | 逃离塔科夫 BOSS 上游原始 JSON（id=1 PVP / id=2 PVE；json.tarkov.dev maps + mobs 精简包 + locale；失败不覆盖） |
| `tarkov_bosses_meta` | BOSS 同步元数据（id 与 raw 对应，含 boss_count 与同步时间） |
| `tarkov_guides_raws` | 逃离塔科夫藏身处 / 以物易物 / 制作上游原始 JSON（id=1 PVP / id=2 PVE；json.tarkov.dev hideout+barters+crafts + locale；失败不覆盖） |
| `tarkov_guides_meta` | 藏身处与交换同步元数据（id 与 raw 对应，含 station_count / barter_count / craft_count 与同步时间） |
| `tarkov_tracker_binds` | 用户 Tarkov Tracker API token（Fernet 加密；摘要：等级 / 阵营 / 已完成任务数；`progress_json` 为每条任务 complete/failed；API 不回传明文 token） |
| `tarkov_raid_rooms` | 战局准备协作房间（大厅公开可进）。`public_id` URL 用；`map_slug` 创建后锁定；`status`=`live`/`archived`；从 `created_at` 起 24 小时可编辑，到期或房主关闭后封存只读留档。`host_user_id` ON DELETE RESTRICT |
| `tarkov_raid_room_members` | 进过房间的人（展示名快照）；复合主键 `(room_id, user_id)`；离开写 `left_at` 不删行。`room_id` / `user_id` ON DELETE CASCADE |
| `tarkov_raid_room_task_claims` | 房间任务勾选并集署名；复合主键 `(room_id, task_id, user_id)`。ON DELETE CASCADE |
| `tarkov_raid_room_marks` | 房间画板（`kind`=`pin`/`line`/`stroke`，地图 `x/z` + `floor`；`stroke` 另存 `points_json` 折线）。索引 `(room_id, created_at)`。ON DELETE CASCADE |
| `minecraft_server_profiles` | 圈子 Minecraft 开服剧本草稿（永远一行 `id=1`：版本 / 加载器 / 核心 / Egg / 启动命令 / 钉死模组 / 配置覆盖；不镜像当前 Pelican 服实时状态。`applied_json` 为上次成功「应用」时的快照；`mod_presets_json` 为模组键值预设（按 tool_id 存用户选定的配置 `directories`，以及 `pins`：`file` 为服内绝对路径且须在这些目录内，加上 key/value；旧整文件草稿忽略）；`mod_inventory_json` 为当前服 jar 库存（打开页对账指纹，增量拆包认亲；与开服剧本 `mods_json` 不是同一份）；本体在 Pelican，不另起进程；公开地址与 RCON 连接在 `system_configs.integrations`，不进开服剧本） |
| `minecraft_perf_samples` | Minecraft RCON 性能采样热数据（约 10 秒一条：TPS/MSPT，以及可选实体总数 / 已加载区块）。只保留约 48 小时，供 30 分钟 / 1 小时折线看尖峰 |
| `minecraft_perf_rollups` | 性能留档：`grain`=`1m`/`1h`/`1d` + `bucket_at` 唯一。分钟桶约留 30 天（12h/24h 折线）；小时/日桶永久（30d / 全部）。每桶含 avg/min/max（实体与区块为 avg/max）。由采集任务刷新当前桶，`job_runs_prune` 回填并删过期原始点 |
| `minecraft_presence_segments` | Minecraft 玩家在线/离线片段（总览时间轴，永久留档）；索引含 `(player_key, started_at)` / `(player_key, ended_at)` |
| `arknights_box_snapshots` | 明日方舟盒子练度快照（按 member + uid 日更；`payload_json` LONGTEXT） |
| `arknights_rogue_raws` | 明日方舟肉鸽 GET `/game/arknights/rogue` 原始 JSON（按 member+uid+topic 最新一份；force / 首次回源） |
| `taygedo_binds` | 塔吉多凭证（加密）；`auto_checkin` 为角色偏好派生摘要 |
| `taygedo_checkin_logs` | 塔吉多社区 APP / 异环 / 幻塔签到记录（`source` status/action；含 `awards_text` / `awards_json`） |
| `taygedo_attendance_raws` | 异环 / 幻塔签到日历（signin/state + sign/rewards）原始 JSON（按 member+game+role 最新一份；跨月或 force / 签到后回源） |
| `exastris_box_raws` | 异环 yh/characters 原始 JSON（按 member+role 最新一份；force / 首次回源） |
| `exilium_binds` | 追放社区凭证（加密）；`auto_checkin` 为角色偏好派生摘要 |
| `exilium_checkin_logs` | 追放社区签到记录（`source` status/action；含 `awards_text` / `awards_json`） |
| `kujiequ_binds` | 库街区凭证（加密）；`auto_checkin` 为角色偏好派生摘要 |
| `kujiequ_checkin_logs` | 库街区社区 / 鸣潮 / 战双签到记录（`source` status/action；含 `awards_text` / `awards_json`） |
| `mihoyo_binds` | 米游社 Cookie/Stoken（加密）；`auto_checkin` 为角色偏好派生摘要 |
| `mihoyo_checkin_logs` | 米游社社区 / 原神 / 崩坏3 / 星铁 / 绝区零等签到记录（`source` status/action；含 `awards_text` / `awards_json`） |
| `mihoyo_attendance_raws` | 原神 / 崩坏3 / 星铁 / 绝区零 / 崩坏2 福利签到日历（info + home）原始 JSON（按 member+game+role 最新一份；跨月或 force / 签到后回源） |
| `kujiequ_attendance_raws` | 鸣潮 / 战双签到日历（initSignInV2 + queryRecordV2）原始 JSON（按 member+game+role 最新一份；跨月或 force / 签到后回源） |
| `kujiequ_ww_box_raws` | 鸣潮 roleBox（baseData + calabashData）组合原始 JSON（按 member+role 最新一份；force / 首次回源） |
| `job_runs` | 轮询 / 签到等任务执行日志；与 `*_checkin_logs` 默认保留 90 天，由定时任务 `job_runs_prune` 清理。该任务同时上卷 Minecraft 性能档。索引含 `(job_key, started_at)` |
| `system_configs` | 系统配置（SMTP、集成密钥、`platform_features` 平台开关、调度等） |
| `register_challenges` | 邮箱验证码挑战；复合主键 `(email, purpose)`，`purpose`=`register` / `bind` / `reset`；`expires_at` 有索引 |
| `oauth_exchange_tickets` | QQ 登录一次性换票码（短 TTL；`access_token` Fernet 加密落库，避免 JWT 进回调 URL）；`expires_at` 有索引 |
| `steam_apps` | Steam AppID → 显示名 / 库封面图标 / 头图 / 国区价格缓存 |

迁移 `20260806_0026` 会一次性清空四平台 `*_checkin_logs` 并曾重置各 bind 的 `last_checkin_*`。`20260826_0066` 已删除 bind 上的 `last_checkin_*` 列（上次执行只信 `*_checkin_logs`）；`checkin_hour` / `checkin_minute` 仍作 prefs 种子保留。不可 `downgrade` 恢复 0026 清掉的数据。

启动时会 DROP 已废弃表：`games` / `match_records` / `cs2_*`。
