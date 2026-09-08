# 生产部署

产品介绍见根 [`README.md`](../README.md)。安全与 Redis 见 [`security.md`](security.md)。改表见 [`database.md`](database.md) 与 [`backend/alembic/README.md`](../backend/alembic/README.md)。

## Linux LXC（推荐）

单副本源码部署。MySQL / MariaDB 自备（塔科夫物品 raw 约 20MB，建议 `max_allowed_packet ≥ 64M`）；可选本机 Redis（限流 / 扫码 KV；不配则进程内降级）。

```bash
git clone https://github.com/739790797/zhange-stats.git /opt/zhange-stats
cd /opt/zhange-stats
cp .env.example .env   # 编辑 DATABASE_URL；建议 REDIS_URL=redis://127.0.0.1:6379/0
bash scripts/install.sh
# 编辑 .env 后：
sudo systemctl start zhange-stats
# 浏览器 http://<LXC>:8000 （或经反代）；安装向导创建管理员
```

## 更新方式（AstrBot 式，仅管理端）

1. 管理端 → **系统更新** → 检查 / 一键更新
2. 进程内下载 GitHub Release 源码 zip + 预构建 `static` → pip（对端掐流会自动重试并尝试续传）
3. **先跑 Alembic 迁移**；失败则回滚白名单代码、**不重启**（避免迁移挂死 → 502）
4. 迁移成功后再 **`os.execv` 同 PID 换码**（无需 `systemctl`、无需 root）
5. 安装树须属服务用户（`zhange`）可写；勿用 root 手改代码属主

应用内更新仅管理员；默认仅 `APP_ENV=production` 允许（可用 `ALLOW_IN_APP_UPDATE` 覆盖）。更新会覆盖白名单路径，不碰 `.env` / `var/` / `data/` / `uploads/` / `.venv`。

应急排障（非常规升级路径）：`sudo systemctl restart zhange-stats`。  
下载被中断、或迁移半完成 / 历史 **Alembic 双 0056** 导致进程起不来、无法用管理端更新时，在主机执行：

```bash
# 推荐：拉主干源码（含自愈）+ 最新 Release 的 static
curl -fsSL https://raw.githubusercontent.com/739790797/zhange-stats/main/scripts/emergency_update.sh | sudo SOURCE_REF=main bash
```

## 部署形态

单 `app` 进程。APScheduler、签到/Steam 进程内锁、启动时 Alembic 迁移均非多实例安全。水平扩展前须另行解决调度选举、共享 `DATA_DIR`/`SECRET_KEY`、迁移单点，以及共享 `REDIS_URL`。**当前请保持单 `app` 副本**。

联机大厅房间 WebSocket（`raid_room_hub`）与三狗位置推送（`goon_tracker_hub`）均为**进程内广播**：多 `app` 副本时 REST 写与 WS 可能落在不同进程，房间事件或出没更新会丢。扩容前须改为 Redis pub/sub（或同类跨进程总线）；在此之前勿水平扩展联机大厅所在服务。

发版：推送到 `main` 时 CI 按根目录 `VERSION` 创建/更新 GitHub Release（tag `v{VERSION}`），并上传 `zhange-stats-{VERSION}-static.tar.gz`。

持久化目录：`var/data/`（含 `.secret_key` 与日志、TexTeller 公式识别权重 `var/data/texteller/`、钥匙截图识别 RapidOCR 权重 `var/data/rapidocr/` 与 EasyOCR 权重 `var/data/easyocr/`）、`var/uploads/`、`.env`（更新白名单不会覆盖）。已有生产若仍用安装根 `data/`、`uploads/`，保持 `.env` 原值即可。相对路径相对安装根，不要往 `backend/`、`frontend/` 写 data/uploads。

公式识别用 [TexTeller](https://github.com/OleehyO/TexTeller) 的 ONNX 权重，推理走 `onnxruntime`（主依赖），不必再装官方 `texteller`（torch）。权重可更新：启动时若本地没有会后台补齐；之后由任务配置「公式识别模型更新」对照镜像上的 `OleehyO/TexTeller` 定时同步。默认走 `https://hf-mirror.com`。

钥匙管理截图识别走站内共享 OCR：[RapidOCR](https://github.com/RapidAI/RapidOCR)（默认 **PP-OCRv5 server**，可在系统管理「文字识别」改 PP-OCRv6 small/medium）和 [EasyOCR](https://github.com/JaidedAI/EasyOCR) 交叉验证，低频场景优先准。依赖在 `requirements.txt`（`rapidocr` + `easyocr` / torch + `opencv-python-headless`）。权重由任务配置「识别模型更新」落到 `var/data/rapidocr` 与 `var/data/easyocr`（Paddle 走 ModelScope，EasyOCR 走 GitHub Release）；识别时不现场下载，未就绪会 503。EasyOCR 常驻大约多占 1–2GB 内存。LXC 若同时装上了 `opencv-python`（带 GUI）可能缺 libGL，可 `pip uninstall -y opencv-python` 只留 headless。可选第三路：`apt install tesseract-ocr tesseract-ocr-chi-sim tesseract-ocr-eng`，有二进制才会启用。不对外提供通用识别 HTTP。

健康检查：`GET /health` 返回 `status` / `database` / `scheduler` / `version`；数据库不通时为 `degraded` 且 **HTTP 503**。数据库探测结果进程内缓存 1 秒，避免探针打满连接池。管理端「平台日志」的运行时健康另含 `APP_ENV`、Redis、`TRUST_X_FORWARDED_FOR`、SMTP，公开引流前应在该页核对。

塔科夫工作台中间用 dump 枪图做底板，在图上点槽位换配件，默认不依赖本机 Chrome。`patchright` 钉死在 `requirements.txt` 里，仅当显式打开 `TARKOV_WORKBENCH_IMAGE_GEN=true` 时才会拉浏览器做出图代理。

## 公开运营检查

对外宣传（例如 B 站）前核对这些项。应用不探测备案状态。

| 项 | 期望 |
|----|------|
| `APP_ENV=production` | 弱管理员口令拒绝启动；关闭 Swagger；禁止 `ALLOW_EMAIL_CODE_LOG` |
| 安全头 / HSTS | 反代（及应用中间件）有 `X-Content-Type-Options`、`Referrer-Policy`、`X-Frame-Options DENY`、`Permissions-Policy`；HTTPS 下 HSTS |
| 最近一次成功备份 | `scripts/backup.sh` 产出日期；演练 restore 的日期记在运维笔记即可 |
| `REDIS_URL` | 生产应配置；否则限流与短时 KV 只在本进程内存，重启即丢 |
| `TRUST_X_FORWARDED_FOR` | **仅**在受信反代之后设 `true`；直接暴露 uvicorn 时保持默认 `false` |
| SMTP | 邮箱注册要能发出验证码；管理端「邮件」里 `configured` |
| 条款 | 站内 `/legal/terms`、`/legal/privacy`；片尾写明非官方、非作弊 |
| ICP 备案 | 国内公开站点在管理端「安全设置」或 `ICP_BEIAN_NO` 填写备案号；留空则全站页脚不展示 |
| 管理端核对 | 「平台日志」运行时健康：`app` / `mysql` / `redis` / `scheduler` / `app_env` / `xff` / `smtp`。生产未配 Redis 或 SMTP 会标降级 |
| 规范对齐 | 安全头、备份、Cookie/CSRF、CSP 等见 [`hardening-roadmap.md`](hardening-roadmap.md)（已落地） |

联机大厅为单进程内存 WebSocket，不要承诺可水平扩展。宣传口径走「队友协作勾任务 / 标点」，不要把截图同步说成实时雷达。限流数字见 [`security.md`](security.md)「塔科夫联机」。

## 反代与静态资源

推荐在 uvicorn 前面放 nginx / Caddy：gzip（或 brotli）压缩 JSON API 与 `text/html`、`text/css`、`application/javascript`；`/assets/`（Vite hashed 文件名）长缓存 `Cache-Control: public, max-age=31536000, immutable`；`index.html` 用 `no-cache`。应用进程也会给 `/assets` 加 immutable 头，无反代时仍可命中浏览器缓存。

示例（nginx）。`add_header` 在有 `location` 时不继承，每个会返回用户响应的 location 都要写：

```nginx
gzip on;
gzip_types text/plain text/css application/json application/javascript text/xml image/svg+xml;

# 安全头（1 期）；CSP 先 Report-Only（7 期）。HSTS 仅 HTTPS。
map $scheme $hsts_header {
    https "max-age=31536000; includeSubDomains";
    default "";
}

location /assets/ {
    alias /opt/zhange-stats/static/assets/;
    expires 1y;
    add_header Cache-Control "public, immutable";
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header X-Frame-Options "DENY" always;
    add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;
    add_header Strict-Transport-Security $hsts_header always;
    add_header Content-Security-Policy-Report-Only "default-src 'self'; script-src 'self' https://static.geetest.com; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https:; connect-src 'self' ws: wss: https:; font-src 'self'; frame-src 'self' https://static.geetest.com https://gcaptcha4.geetest.com; worker-src 'self' blob:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; report-uri /api/csp-report" always;
}

location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_read_timeout 360s;
    proxy_send_timeout 360s;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header X-Frame-Options "DENY" always;
    add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;
    add_header Strict-Transport-Security $hsts_header always;
    add_header Content-Security-Policy-Report-Only "default-src 'self'; script-src 'self' https://static.geetest.com; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https:; connect-src 'self' ws: wss: https:; font-src 'self'; frame-src 'self' https://static.geetest.com https://gcaptcha4.geetest.com; worker-src 'self' blob:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; report-uri /api/csp-report" always;
}
```

应用进程也会发同一套头与 `X-Request-ID`（无反代时仍可用）。把 `CSP_ENFORCE=true` 后，应用改发 `Content-Security-Policy`；nginx 把上面的 `Report-Only` 换成 enforce 名。观察 `zhange.csp` 日志无误杀联机 WS / 地图 / KaTeX / 极验 / OCR worker 后再 enforce。策略须放行 `static.geetest.com` 脚本与 iframe，以及 `worker-src 'self' blob:`（塔科夫 OCR）。

## 备份与恢复

对象：MySQL（`mysqldump --single-transaction`）、`var/data/`（含 `.secret_key`）、`var/uploads/`、安装根 `.env`（不要进 Git）。

- 备份：`sudo ./scripts/backup.sh`（读 `.env` 的 `DATABASE_URL`，默认写到 `/var/backups/zhange/zhange-时间戳.tar.gz`，保留 14 天）。可用 `ZHANGE_BACKUP_DIR`、`ZHANGE_BACKUP_KEEP_DAYS` 覆盖。
- 恢复：`sudo ZHANGE_RESTORE_CONFIRM=YES ZHANGE_RESTORE_ARCHIVE=/var/backups/zhange/zhange-时间戳.tar.gz ./scripts/restore.sh`（停 `zhange-stats.service` → 导库 → 解压 `var/` 与 `.env` → 启动）。
- systemd timer 示例（每日 03:15）：

```ini
# /etc/systemd/system/zhange-backup.service
[Service]
Type=oneshot
ExecStart=/opt/zhange-stats/scripts/backup.sh

# /etc/systemd/system/zhange-backup.timer
[Timer]
OnCalendar=*-*-* 03:15:00
Persistent=true
[Install]
WantedBy=timers.target
```

演练：在非生产或停机窗口 restore 到临时库，确认能登录；把成功日期记在运维笔记即可，不必把备份文件提交进仓库。

请求排障：响应头 `X-Request-ID` 与 journal / 平台日志同一编号。前端白屏会 `POST /api/client-errors`（需登录，限流），写入运行时日志。

## Minecraft / Pelican

圈子只有 Pelican 里那一台服。战鸽不另开 Java。在管理端「集成密钥」填 Panel 根地址、Client API Token（需 files + power）、Server UUID，以及 RCON 地址/端口/密码（服内自行 `enable-rcon`，不要对公网开放）。首次把 Egg 启动改成 `bash zhange/boot.sh <原来的 java 命令>`（示例见页面提示）。写操作走 Pelican Client API，与网页同一入口；在线人数是对公开端口的 status ping，TPS/MSPT 走 RCON。模组版本钉死，不会每次开服拉 latest。
