# 战鸽数据

开源的圈子成员站：把多平台签到与养成盒、Steam 游玩统计，以及塔科夫图鉴、Minecraft 单服代操收在同一处。公开的 **战鸽酒馆** 可以读文章，登录后可以评论。

本仓库与任何游戏厂商、发行商或官方社区无关，是自用圈子的非官方第三方工具。图鉴与攻略数据来自社区开源项目，可能滞后或不完整。逃离塔科夫相关能力只做查阅与队友协作勾任务 / 标点，不提供作弊。

可自托管。本地开发见 [`docs/develop.md`](docs/develop.md)，生产部署见 [`docs/deploy.md`](docs/deploy.md)；文档总目录在 [`docs/`](docs/README.md)。

## 能做什么

- **账号**：邮箱注册 / 登录，或 QQ 互联；站内头像、昵称与 Steam 资料分开。
- **Steam**：绑定后记录游戏中会话；按日看时间轴，按周 / 月 / 年看热力日历。圈子成员可互看。
- **我的日常**：已加入本站的各平台签到任务与今日奖励。
- **战鸽酒馆**：公开文章站。未登录可读；登录后可评论。
- **签到平台**：森空岛、塔吉多、库街区、米游社、追放。绑定后可手动签到或按角色定时自动签到；部分平台支持兑换与养成盒。
- **逃离塔科夫**：物品、任务、商人、BOSS、地图等社区图鉴；联机房间供队友协作勾任务、标点、声明钥匙。游戏日志在浏览器本机解析，服务器只存摘要。
- **Minecraft**：圈子单服代操（服况、启停、文件与模组工具）。

管理员可配置用户、任务、调度、集成密钥与站点设置。

## 致谢

图鉴、日历与部分上游协议对齐下列开源项目。没有它们，这些功能做不出来。

**逃离塔科夫**

- [tarkov.dev](https://tarkov.dev)（[the-hideout/tarkov-dev](https://github.com/the-hideout/tarkov-dev)）— json dump 图鉴数据
- [the-hideout/tarkov-dev-svg-maps](https://github.com/the-hideout/tarkov-dev-svg-maps) — 互动地图底图
- [tarkovtracker-org/tarkov-data-overlay](https://github.com/tarkovtracker-org/tarkov-data-overlay) — 社区 overlay

**明日方舟 / 终末地**

- [yuanyan3060/ArknightsGameResource](https://github.com/yuanyan3060/ArknightsGameResource) — 干员 `character_table`
- [jacket-sikaha/game-schedule](https://github.com/jacket-sikaha/game-schedule) — 活动日历

**签到上游对齐**

- [Womsxd/MihoyoBBSTools](https://github.com/Womsxd/MihoyoBBSTools) — 米游社签到协议
- [Ljzd-PRO/nonebot-plugin-mystool](https://github.com/Ljzd-PRO/nonebot-plugin-mystool) — 米游币商城接口
- [TomyJan/Kuro-API-Collection](https://github.com/TomyJan/Kuro-API-Collection) — 库街区接口整理

**字体（SIL Open Font License 1.1）**

- [IBM Plex Sans / Mono](https://github.com/IBM/plex) — 塔科夫壳拉丁字重
- [Rajdhani](https://github.com/itfoundry/rajdhani) — 塔科夫壳标题字重

游戏内容与商标归各权利方所有。
