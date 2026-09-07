# 从 Halo 导入战鸽酒馆文章

导入**不解析 `.sql` 文本**（Halo 2 正文在 BLOB/JSON 里）。把 dump 恢复到临时 MariaDB，再让本命令连那台库。

在 `backend/` 目录、已激活虚拟环境：

```bash
python -m app.services.articles.halo_import \
  --source-url mysql+pymysql://user:pass@127.0.0.1:3306/halo \
  --author-map '{"halo用户名或邮箱": 本站user_id}' \
  --default-author-id 1 \
  --uploads /path/to/halo/upload \
  --dry-run
```

去掉 `--dry-run` 才真正写入战鸽库。`--author-map` 也可以是 JSON 文件路径。对照表缺省的作者会落到 `--default-author-id`，并打 warning。

- 自动探测 Halo 1.x（`posts`）或 2.x（`extensions`）
- `halo_source_id` 保证可重复跑
- `--uploads` 指向 Halo 的 `upload/`（或附件目录）；复制到 `var/uploads/articles/halo/` 并改写正文 URL
- **只有 SQL、没有附件目录时，文能进来，图会裂**
