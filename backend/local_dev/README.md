# 本地假数据（CLI）

假监控已从管理端移除。若本地仍需灌演示 Steam 数据，请用 CLI：

```bash
python -m local_dev.seed_local
python -m local_dev.seed_local --wipe
python -m local_dev.seed_local --reseed-history
python -m local_dev.seed_local --purge-fake   # 仅删除 user_a～z 及历史，不重建
```

登录示例：`user_a` / `demopass123`

说明：

- 仅用于开发灌数；生产调度不再读取假监控开关
- 建议仍配置 `STEAM_API_KEY`（补库列表 icon 等）
- 历史默认覆盖「上个月 1 日～今天」
