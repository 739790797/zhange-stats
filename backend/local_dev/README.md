# 本地假监控 / 假数据

启用：

1. 登录管理员 → **系统管理 → 定时任务** → 打开「本地假监控」→ 保存并应用  
   （会幂等补齐演示账号，并按 Steam 任务间隔跑假轮询）
2. 可选手动灌数：
   - `python -m local_dev.seed_local`
   - `python -m local_dev.seed_local --wipe`
   - `python -m local_dev.seed_local --reseed-history`（清空并重生成历史）

兼容：`.env` 仍可设 `STEAM_FAKE_POLL=true` 作为冷启动默认（未在系统界面保存过时生效）。

登录示例：`user_a` / `demopass123`

作息类别：

| 用户 | 类别 |
|------|------|
| A–I | 大学生（午间/傍晚碎片 + 晚间高峰） |
| J–R | 上班族（工作日晚间为主，周末更长） |
| S–Z | 游戏主播（下午场 + 夜间长播） |

说明：

- **假监控只伪造用户在线/游玩状态**；游戏 icon、商店卡片、名称等仍走与正式环境相同的真实请求
- 建议仍配置 `STEAM_API_KEY`（补库列表 icon 等）；无 Key 时 icon 会走公开 appinfo 兜底
- 历史默认覆盖「上个月 1 日～今天」，含游玩 / 在线 / 离线
- 假状态会从库内未结束会话恢复，重启不会每次新开一局
- 与真实 Steam 轮询互斥（开启假监控时不会跑真实 presence poll）
