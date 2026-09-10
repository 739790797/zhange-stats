# 本地假数据（CLI）

假监控已从管理端移除。若本地仍需灌演示数据，请用 CLI：

```bash
python -m local_dev.seed_local
python -m local_dev.seed_local --wipe
python -m local_dev.seed_local --reseed-history
python -m local_dev.seed_local --purge-fake   # 仅删除 user_a～z 及历史，不重建
python -m local_dev.seed_tavern               # 酒馆示例文
python -m local_dev.seed_now_playing          # 「正在游玩」演示会话（source=demo）
```

登录示例：`user_a` / `demopass123`（Steam 假用户）；`demo_viewer` / `demopass123`（正在游玩演示）。

说明：

- 仅用于开发灌数；生产调度不再读取假监控开关
- 建议仍配置 Steam API Key（补库列表 icon 等）
- 历史默认覆盖「上个月 1 日～今天」
- 探测脚本与上游样例 JSON 不入库
