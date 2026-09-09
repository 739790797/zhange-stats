# 运行时目录（本文件入库，其余内容不入库）

应用运行时、缓存、本地开发进程文件一律写在这里，**不要**写进 `backend/` 或 `frontend/`。

| 子目录 | 用途 |
|--------|------|
| `data/` | `DATA_DIR`：`.secret_key`、应用 JSONL 日志、更新锁、更新临时包、TexTeller / RapidOCR / EasyOCR 权重（`ocr_REVISION`；旧戳 `key_ocr_REVISION` 仍可读） |
| `uploads/` | `UPLOAD_DIR`：站内头像 `avatars/`、酒馆配图/附件 `articles/` |
| `dev/` | `run` / `restart` 的 pid 与 stdout（Windows 与无 systemd 的 Linux） |
| `backups/` | `backup` 默认输出目录 |
| `mariadb/` | Windows 便携 MariaDB（发行包 `dist/`、数据目录 `data/`、`provision.json`） |
| `cache/` | pytest / Vite / `PYTHONPYCACHEPREFIX` |
| `tmp/` | 本地探测用的临时目录 |

生产若 `.env` 已指向安装根 `data/`、`uploads/`（旧布局），继续用那些绝对路径，不必搬家。
新本地克隆与新安装默认使用 `var/data`、`var/uploads`。

管理端「运行维护 → 文件管理」统计这些目录的磁盘占用，并可进入白名单根浏览（密钥文件不可下载）。

`frontend/src/data/` 是源码资源（如塔科夫地图 JSON），不是运行时。
`frontend/src/api/generated/` 是提交进仓库的 OpenAPI 契约，不是缓存。
