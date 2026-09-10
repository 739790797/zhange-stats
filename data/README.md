# 运行时目录（本文件入库，其余内容不入库）

应用运行时、模型、缓存、本地开发进程文件一律写在安装根 `data/`，**不要**写进 `backend/` 或 `frontend/`。
`frontend/src/data/` 是源码资源（如塔科夫地图 JSON），不是本目录。

启动时 `migrate_runtime_layout` 会把旧的 `var/`（以及曾经当 `DATA_DIR` 用的扁平 `data/`）拆进下表，并清根 `config.example/`、空壳旧目录、未使用的 TexTeller ONNX。不要再出现 `data/data`。根 `.env` 与可能不同的旧 `.secret_key` 不自动删。

| 子目录 | 用途 |
|--------|------|
| `runtime/` | `DATA_DIR`：`.secret_key`、应用 JSONL 日志、更新锁 / `update-tmp`、SQLite 时的 `zhange.sqlite` |
| `uploads/` | `UPLOAD_DIR`：站内头像 `avatars/`、酒馆配图/附件 `articles/` |
| `models/` | 下载权重：TexTeller、RapidOCR、EasyOCR（含 `ocr_REVISION`；旧戳 `key_ocr_REVISION` 仍可读） |
| `run/` | `run` / `restart` 的 pid 与 stdout（Windows 与无 systemd 的 Linux） |
| `backups/` | `backup` 默认输出目录 |
| `mariadb/` | Windows 便携 MariaDB（发行包 `dist/`、数据目录 `data/`、`provision.json`） |
| `cache/` | pytest / Vite / pip / Hugging Face / Torch / EasyOCR 模块缓存、`PYTHONPYCACHEPREFIX`、工作台 Playwright profile。启动时会把家目录里**战鸽能认出来的**权重拷进来（TexTeller 仓库、EasyOCR 模型文件）；不搬整个 `~/.cache/huggingface` |
| `tmp/` | 更新解包、备份暂存、进程 tempfile |

备份打包 `config/`、`runtime/`、`uploads/`、`models/`；不打包 `cache/`、`run/`、`tmp/`、`mariadb/`。

管理端「运行维护 → 文件管理」统计这些目录的磁盘占用，并可从安装根点进去增删改查。密钥、MariaDB 数据目录与备份仍不可下载/改/删；`.git`、`config/` 等普通目录可进可删。
`frontend/src/api/generated/` 是提交进仓库的 OpenAPI 契约，不是缓存。
