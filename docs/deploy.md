# 生产部署

产品介绍见根 [`README.md`](../README.md)。安全与 Redis 见 [`security.md`](security.md)。改表见 [`database.md`](database.md) 与 [`backend/alembic/README.md`](../backend/alembic/README.md)。

## Linux LXC（推荐）

单副本源码部署。`install` / `run` **不**自动装 MariaDB。首次启动进入安装向导：可选 SQLite（`data/runtime/zhange.sqlite`）或填写外部 MySQL/MariaDB 连接串。存量 LXC 若根上还有 `.env` 的 `DATABASE_URL`，启动会迁入 `config/database.json`，不会重跑选库；迁完可以删掉 `.env`。可选本机 Redis（限流 / 扫码 KV；不配则进程内降级）。塔科夫物品 raw 约 20MB，外部 MariaDB 建议 `max_allowed_packet ≥ 64M`。

```bash
git clone https://github.com/739790797/zhange-stats.git /opt/zhange-stats
cd /opt/zhange-stats
sudo bash scripts/linux/install.sh   # 系统包、venv、当前 VERSION 的预构建 static、systemd 单元
sudo bash scripts/linux/run.sh       # 向导未完成时会打印安装令牌
# 浏览器打开站点（公开前放 HTTPS 反代，见下文）；向导填安装令牌、选库并创建管理员
# 之后重启：sudo bash scripts/linux/restart.sh
# 之后更新：sudo bash scripts/linux/update.sh
```

已有远程库：向导填 `mysql+pymysql://` 连接串，或把连接写进 `config/database.json`（不要覆盖已有文件以外的手工 JSON）。本机 MariaDB 若仍需要，手工跑 `scripts/common/provision_mariadb.py`。

- **Python 3.11+**：Debian 12 自带 3.11，Ubuntu 24.04 自带 3.12。系统 `python3` 更旧时先装 `python3.11` 与 `python3.11-venv`，再 `sudo ZHANGE_PYTHON=python3.11 bash scripts/linux/install.sh`。已有的 `backend/.venv` 低于 3.11 时脚本会停下，删掉它后重跑 `install`。
- **前端 static**：`static/` 不入库。`install.sh` 发现 `static/index.html` 不存在时，下载当前 `VERSION` 对应 Release 的 `zhange-stats-<VERSION>-static.tar.gz`，校验 sha256 后放进 `static/`（不需要数据库）；有 systemd 单元时 `run.sh` / `restart.sh` 也会补一次。下载失败只告警、后端照常启动，但页面在补上 `static/` 之前打不开。补救：`sudo bash scripts/linux/update.sh --static-only --proxy <GitHub 代理前缀>` 重试；主干上的 `VERSION` 可能还没发版，可 `git fetch --tags` 后检出已发布的 tag 再 `install`；或本机 `cd frontend && npm ci --legacy-peer-deps && npm run build`，把 `frontend/dist/` 里的文件复制到 `static/`。
- **安装令牌**：向导要求填写 `data/runtime/setup-token` 的内容（0600，只在服务器上）。`run.sh` / `restart.sh` 在向导未完成时把它打印出来；读不到时 `sudo cat` 该文件。向导完成后令牌自动删除。
- **属主**：以 root 跑 `install` / `run` / `restart` / `update` 时，建 venv、pip、npm、站点配置同步和更新器都以服务用户 `zhange` 身份执行（`runuser`）。脚本退出时（失败也算）会把安装树里属主不对的文件改回 `zhange`，`data/mariadb/` 除外。

### systemd 单元与 `config/systemd.env`

`install.sh` / `update.sh` 把 `scripts/linux/zhange-stats.service` 写进 `/etc/systemd/system/`。单元自带 `APP_ENV=production`。进程环境变量优先于 `config/app.json`，所以管理端「运行环境」里的 `APP_ENV` 对这个单元只读。生产模式下会话 Cookie 带 `Secure`：除了向导创建管理员那一次，用纯 HTTP 打开站点保持不了登录。公开前须放 HTTPS 反代（见「反代与静态资源」）。只想在内网用 HTTP 试用时，在 `config/systemd.env` 写 `APP_ENV=development` 再重启。

进程级变量写在 `config/systemd.env`，每行一个 `KEY=VALUE`。单元用 `EnvironmentFile=-` 读取，文件不存在也照常启动，同名时覆盖单元里的默认值。改完执行 `sudo bash scripts/linux/restart.sh` 生效。

| 变量 | 单元默认 | 说明 |
|------|----------|------|
| `APP_ENV` | `production` | 见上 |
| `UVICORN_HOST` | `0.0.0.0` | 只经本机反代访问时改成 `127.0.0.1` |
| `UVICORN_PORT` | `8000` | 监听端口 |
| `FORWARDED_ALLOW_IPS` | `127.0.0.1` | uvicorn `--proxy-headers` 只采信这些地址发来的 `X-Forwarded-For` / `X-Forwarded-Proto`。反代在另一台机器上时写它的 IP |

单元另带 `--ws-max-size 4194304`（WebSocket 帧上限 4 MiB）、`NoNewPrivileges=yes`、`UMask=0027`（新文件只给属主和同组读）、`LimitNOFILE=65536`。存量安装要用上新单元，跑一次 `sudo bash scripts/linux/install.sh` 或 `update.sh`。管理端一键更新改不到 `/etc` 下的单元。

## Windows 本机部署

公开生产仍推荐 Linux LXC（管理端一键更新、systemd）。Windows 用于开发机或单机自托管。需要 Python 3.11+、Node 18+。首次 `run` 打开向导选 SQLite 或外部库。本机 MariaDB 改为手工 `scripts/common/provision_mariadb.py`（便携包仍落到 `data/mariadb/`）。

```powershell
git clone https://github.com/739790797/zhange-stats.git
cd zhange-stats
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\win\install.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\win\run.ps1
```

脚本不区分生产/开发、也没有 `-Production`。要当生产跑，在管理端「运行环境」或 `config/app.json` 设 `APP_ENV=production` 后重启。`install` / `run` / `restart` / `update` 都会检查依赖：`requirements.txt` / `constraints.txt` 与上次安装相同（`backend\.venv\.zhange-req.stamp`）就跳过 pip，`backend\.venv` 低于 Python 3.11 时停下。`install.ps1` 也会尝试下载当前 `VERSION` 的预构建 static；`run.ps1` 走 Vite（:6131），用不到它，只有配置了 `STATIC_DIR` 时后端才托管 `static\`。要补 static 时执行 `update.ps1 -StaticOnly -Proxy <GitHub 代理前缀>`。`run.ps1` / `restart.ps1` 在向导未完成时打印安装令牌。

## 更新方式

生产日常可用管理端「系统更新」（仅管理员；默认 `APP_ENV=production`，可用 `ALLOW_IN_APP_UPDATE` 覆盖）。主机脚本与管理端走**同一套** GitHub Release：

1. 下载源码包 `zhange-stats-<VERSION>-source.tar.gz` 与预构建 `static`，逐个校验 sha256：以 Release 资产自带的 digest 为准，并与 `SHA256SUMS` 交叉核对；两者不一致或都没有就中止。没有源码包的旧 Release 回退 GitHub zipball，这一份无法校验，日志会写明。对端掐流会自动重试并尝试续传。默认目标是版本号最高的正式 Release（不含草稿与预发布），资产按完整文件名匹配。
2. 解压到 `data/runtime/update-tmp`，static 先解到 `static.new`。`requirements.txt` / `constraints.txt` 与上次安装不同（对照 `backend/.venv/.zhange-req.stamp`）才 pip；pip 失败时代码不动，当前版本继续运行。
3. 先给当前白名单代码做快照，再整棵替换（**增 / 改 / 删** `backend/app`、`alembic`、`scripts` 等）；`frontend/` 按文件同步（保留 `node_modules` / `dist`）；不碰 `config/` / `data/` / `.venv`（存量 `.env` 也不覆盖）。落盘后以及随后启动会清根 `config.example/`、`deploy/`、空壳旧目录、未使用的 TexTeller ONNX；**不会**删根 `.env` 或可能不同的旧 `.secret_key`
4. **先跑 Alembic 迁移**；落盘或迁移失败都从快照回滚代码、**不重启**（避免迁移挂死 → 502），`static/` 也不动
5. 迁移成功后把 `static.new` 换成 `static/`（旧版留在 `static.prev`），写入 pip 戳。管理端 **`os.execv` 同 PID 换码**；主机 `update`（root）会把 `scripts/linux/zhange-stats.service` 写进 `/etc` 再 `restart`（有 systemd 则 `systemctl`，否则 6130/6131）。管理端更新碰不到 `/etc`，0.5.1 升上来后请另跑一次 `install.sh` 刷新单元

```bash
sudo bash scripts/linux/update.sh              # 升到最新 Release
sudo bash scripts/linux/update.sh --check      # 只看是否有新版本
sudo bash scripts/linux/update.sh --version v0.5.3
sudo bash scripts/linux/update.sh --force      # 已是该版本也重新落盘
sudo bash scripts/linux/update.sh --no-restart # 只落盘，稍后自己 restart
sudo bash scripts/linux/update.sh --static-only            # 只补当前 VERSION 的预构建 static（不改代码、不要数据库、不重启）
sudo bash scripts/linux/update.sh --proxy <GitHub 代理前缀> # 直连 GitHub 不通时
```

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\win\update.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\win\update.ps1 -Check
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\win\update.ps1 -Version v0.5.3
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\win\update.ps1 -Force
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\win\update.ps1 -StaticOnly
```

安装树须属服务用户（`zhange`）可写；勿用 root 手改代码属主。`update.sh` 以 `zhange` 身份跑更新器，结束时（失败或 `--no-restart` 也一样）把属主修回 `zhange`。应用内更新仅管理员。

下载被中断、或迁移半完成 / 历史 **Alembic 双 0056** 导致进程起不来、无法用管理端更新时，在主机安装树内跑 `update`（不要用 curl 管道拉外部脚本覆盖本机）。Git 工作树应急仍可用 `git pull` 后 `install` + `restart`；正式安装只吃上一成功 GitHub Release，`git pull` 主干可能含尚未过门的提交。

## 发版

对外可见的版本 = **质量门绿之后写上的 GitHub Release**。门红则 `publish-release` 不跑：不新建、不覆盖 tag，生产「检查更新」仍是上一成功版，**和没发一样**。

推送到 `main` 时，CI 先跑 `frontend-quality`、`backend-tests`、`backend-migrate-mariadb`（MariaDB 上空库迁移两遍、`alembic check`、迁移测试）、`openapi-drift`；全部通过后才按根目录 `VERSION` 发 Release（tag `v{VERSION}`，建在本次提交上），上传三个资产：

- `zhange-stats-{VERSION}-static.tar.gz`：预构建前端
- `zhange-stats-{VERSION}-source.tar.gz`：`git archive` 源码包，单一顶层目录 `zhange-stats-{VERSION}/`
- `SHA256SUMS`：上面两个文件的 sha256，更新器与资产 digest 交叉核对

Release 发出后不再改动：tag `v{VERSION}` 已存在时（包括上次发到一半），`publish-release` 只留一条 notice「bump VERSION to release」然后跳过，不覆盖、不补传资产。

- 同一轮发版用同一个 `VERSION` 修到绿；绿之前不会建 tag。发出去以后再要发，就得改 `VERSION`。
- 发到一半失败（tag 已建、资产不全）：改 `VERSION` 重新发，不要手工补传资产或打 tag。
- 只有准备让生产看见新版本时才改 `VERSION`。
- 只在 `main` 上发版；在别的分支手动触发 workflow 只跑质量门。
- 不要在 CI 红时点管理端更新，也不要手工打 tag。
- workflow 默认只给只读 token，只有 `publish-release` 有 `contents: write`；第三方 action 钉 commit SHA，行尾注释是版本号，升级时一起改。

安装与一键更新吃的是 Release 源码包 + static，不是红掉的 `main` 提交。

## 部署形态

单 `app` 进程。APScheduler、签到/Steam 进程内锁、启动时 Alembic 迁移均非多实例安全。水平扩展前须另行解决调度选举、共享 `DATA_DIR`/`SECRET_KEY`、迁移单点，以及共享 `REDIS_URL`。**当前请保持单 `app` 副本**。

联机大厅房间 WebSocket（`raid_room_hub`）与三狗位置推送（`goon_tracker_hub`）均为**进程内广播**：多 `app` 副本时 REST 写与 WS 可能落在不同进程，房间事件或出没更新会丢。扩容前须改为 Redis pub/sub（或同类跨进程总线）；在此之前勿水平扩展联机大厅所在服务。

持久化目录：`config/`（站点设置，gitignore）。模板在 `scripts/config.example/`，每个 JSON 有 `_version`；`install` / `run` / `restart` / `update` 与启动会把模板里的新键补进已有文件，不覆盖用户值，也不会用模板新建 `database.json`。`data/runtime/`（含 `.secret_key` 与日志、SQLite 时的 `zhange.sqlite`）、`data/uploads/`、`data/models/`（TexTeller / RapidOCR / EasyOCR 权重）。更新白名单不会覆盖 `config/` 与 `data/`。存量安装第一次启动会把旧 `var/` 迁进这套布局，并把根 `.env` 与库内 `system_configs` 迁入 `config/`（不覆盖已有 JSON；迁完可删 `.env`）。相对路径相对安装根，不要往 `backend/`、`frontend/` 写 data/uploads。

公式识别用 [TexTeller](https://github.com/OleehyO/TexTeller) 的 ONNX 权重，推理走 `onnxruntime`（主依赖），不必再装官方 `texteller`（torch）。权重可更新：启动时若本地没有会后台补齐；之后由任务配置「公式识别模型」对照镜像上的 `OleehyO/TexTeller` 定时同步。默认走 `https://hf-mirror.com`。

钥匙管理与局前任务页截图识别走站内共享 OCR：[RapidOCR](https://github.com/RapidAI/RapidOCR)（默认 **PP-OCRv5 server**，站点设置「文字识别」从本机 RapidOCR onnx 清单选档位）和 [EasyOCR](https://github.com/JaidedAI/EasyOCR)（钥匙箱默认交叉验证；局前任务默认只开熊猫）。低频场景优先准。依赖在 `requirements.txt`（`rapidocr` + `easyocr` / **CPU** torch + `opencv-python-headless`）。安装与一键更新会先装官方 CPU 轮，避免 EasyOCR 从 PyPI 拉数 GB CUDA。权重由「文字识别」页检查更新或任务配置「识别模型更新」落到 `data/models/rapidocr` 与 `data/models/easyocr`（Paddle 走 ModelScope，EasyOCR 走 GitHub Release）；识别时不现场下载，未就绪会 503。EasyOCR 常驻大约多占 1–2GB 内存。LXC 若同时装上了 `opencv-python`（带 GUI）可能缺 libGL，可 `pip uninstall -y opencv-python` 只留 headless。不对外提供通用识别 HTTP。

健康检查：`GET /health` 返回 `status` / `database` / `scheduler` / `version`；未选库时 **HTTP 200** 且 `status=setup`、`database=unconfigured`。数据库不通时为 `degraded` 且 **HTTP 503**。数据库探测结果进程内缓存 1 秒，避免探针打满连接池。管理端「运行维护 → 运行环境」可改数据库 / Redis / `APP_ENV` / CORS，并探活当前进程的库与 Redis；公开引流前应在该页核对。SMTP 在「站点设置 → 邮箱设置」。

塔科夫工作台中间用 dump 枪图做底板，在图上点槽位换配件，默认不依赖本机 Chrome。`patchright` 钉死在 `requirements.txt` 里，仅当显式打开 `TARKOV_WORKBENCH_IMAGE_GEN=true` 时才会拉浏览器做出图代理。

## 公开运营检查

对外宣传（例如 B 站）前核对这些项。应用不探测备案状态。

| 项 | 期望 |
|----|------|
| `APP_ENV=production` | systemd 单元默认就是；弱管理员口令拒绝启动；关闭 Swagger；禁止 `ALLOW_EMAIL_CODE_LOG`；会话 Cookie 带 `Secure`，站点须走 HTTPS |
| 安全头 / HSTS | 反代（及应用中间件）有 `X-Content-Type-Options`、`Referrer-Policy`、`X-Frame-Options DENY`、`Permissions-Policy`；HTTPS 下 HSTS |
| 最近一次成功备份 | `scripts/linux/backup.sh` 产出日期；演练 restore 的日期记在运维笔记即可 |
| `REDIS_URL` | 生产应配置；否则限流与短时 KV 只在本进程内存，重启即丢 |
| 客户端 IP | 单元用 `--proxy-headers` + `FORWARDED_ALLOW_IPS=127.0.0.1`：本机反代时限流已按真实 IP 计，`TRUST_X_FORWARDED_FOR` 保持默认 `false`；反代在别的机器上时把它的 IP 写进 `config/systemd.env` 的 `FORWARDED_ALLOW_IPS`。直接暴露 uvicorn 时不要设 `TRUST_X_FORWARDED_FOR=true` |
| SMTP | 邮箱注册要能发出验证码；管理端「邮件」里 `configured` |
| 条款 | 站内 `/legal/terms`、`/legal/privacy`；片尾写明非官方、非作弊 |
| ICP 备案 | 国内公开站点在管理端「安全设置」或 `ICP_BEIAN_NO` 填写备案号；留空则全站页脚不展示 |
| 管理端核对 | 「运行维护 → 运行环境」：数据库 / Redis；生产未配 Redis 会标降级。SMTP 在邮箱设置 |
| 规范对齐 | 安全头、备份、Cookie/CSRF、CSP 等见 [`hardening-roadmap.md`](hardening-roadmap.md)（已落地） |

联机大厅为单进程内存 WebSocket，不要承诺可水平扩展。宣传口径走「队友协作勾任务 / 标点」，不要把截图同步说成实时雷达。请求次数限流默认开启（`config/app.json` 的 `RATE_LIMIT_ENABLED`，紧急时可在「运行环境」关闭），额度见 [`security.md`](security.md)；开了 `TRUST_X_FORWARDED_FOR` 时取 `X-Forwarded-For` 最右一跳。

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

# 文件管理上传（≤256MB）与 Minecraft 文件上传（≤64MB）；应用按路由再限一次
location ~ ^/api/(settings/files|guides/minecraft/files)/upload$ {
    client_max_body_size 260m;
    proxy_request_buffering off;
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 360s;
    proxy_send_timeout 360s;
}

location / {
    # 应用默认请求体上限 8MB，最大的是酒馆附件 10MB；nginx 默认 1m 会把头像、配图、截图识别挡在外面
    client_max_body_size 16m;
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

`/assets/` 的 `alias` 要 nginx 进程能读到安装树：`install.sh` 把安装根设为 `750`（属 `zhange`），单元 `UMask=0027`，nginx 的 `www-data` 默认进不去，会返回 403。二选一：`sudo usermod -aG zhange www-data` 后重启 nginx；或者删掉这个 `location`，让应用出 `/assets`（应用同样带 immutable 头）。反代与 uvicorn 不在同一台机器时，把反代 IP 写进 `config/systemd.env` 的 `FORWARDED_ALLOW_IPS`，否则 `X-Forwarded-Proto` / `X-Forwarded-For` 不被采信。

应用进程也会发同一套头与 `X-Request-ID`（无反代时仍可用）。把 `CSP_ENFORCE=true` 后，应用改发 `Content-Security-Policy`；nginx 把上面的 `Report-Only` 换成 enforce 名。观察 `zhange.csp` 日志无误杀联机 WS / 地图 / KaTeX / 极验后再 enforce。策略须放行 `static.geetest.com` 脚本与 iframe，以及 `worker-src 'self' blob:`（地图等仍可能用 Worker）。塔科夫截图识别已走服务端，不再需要浏览器 OCR worker。

## 备份与恢复

对象：`config/`、`data/runtime/`（含 `.secret_key` 与 SQLite 时的 `zhange.sqlite`）、`data/uploads/`、`data/models/`，外加 `manifest.json`（备份时的 `VERSION`、库里的 Alembic 版本、代码的迁移 head）。MySQL/MariaDB 另打 `zhange.sql`（`mysqldump --single-transaction`，utf8mb4；密码只经 `MYSQL_PWD` 交给客户端，不进命令行）。SQLite 用在线备份 API 取一致副本，不直接拷正在写的库文件与 `-wal`；库文件配在 `data/` 之外时也会打进归档，恢复时放回原路径。不打包：`data/runtime/` 下的 `update-tmp/`、`update.lock`、`setup-token`（以及旧布局遗留的 `tmp/`、`cache/`、`tarkov_pw_profile/`），`__pycache__`、下载到一半的权重 `*.part`，以及 `data/cache`、`data/tmp`、`data/run`、`data/mariadb`。若备份里还有 `.env` 会打包装上以便迁入；旧 tar 里的 `var/data`、`var/uploads` 恢复时会落到新布局。

备份与恢复的实际工作由 `scripts/common/backup_util.py` 完成（只用标准库，系统 Python 即可，不再依赖 `tar` 命令）。归档权限 `0600`，备份目录 `0700`。

- 备份：`sudo ./scripts/linux/backup.sh`（读 `config/database.json` 或环境变量 `DATABASE_URL`，默认写到本安装树 `data/backups/zhange-时间戳.tar.gz`，保留 14 天）。可用 `ZHANGE_BACKUP_DIR`、`ZHANGE_BACKUP_KEEP_DAYS` 覆盖。Windows：`scripts\win\backup.ps1`。
- 恢复：`sudo ZHANGE_RESTORE_CONFIRM=YES ZHANGE_RESTORE_ARCHIVE=/opt/zhange-stats/data/backups/zhange-时间戳.tar.gz ./scripts/linux/restore.sh`。顺序：安全解包（拒绝绝对路径、`..` 与越界链接）→ 对照 `manifest.json` 核对版本 → 停应用 → 导库 → 换 `config/` 与 `data/` → 以 root 跑时把属主修回 `zhange` → 启动。导库失败时 `config/` 与 `data/` 不动、应用保持停止，处理后重跑。Windows 同样设置这两个环境变量后执行 `scripts\win\restore.ps1`。
- 版本核对只告警、不拦：备份的 `VERSION` 与当前代码不同会提示；库的迁移版本在当前代码里找不到（备份比代码新）时，恢复后应用起不来，应先 `update` 到备份时的版本或更新的版本；库比代码旧则启动时自动迁移。没有 `manifest.json` 的旧备份跳过核对。
- systemd timer 示例（每日 03:15）：

```ini
# /etc/systemd/system/zhange-backup.service
[Service]
Type=oneshot
ExecStart=/opt/zhange-stats/scripts/linux/backup.sh

# /etc/systemd/system/zhange-backup.timer
[Timer]
OnCalendar=*-*-* 03:15:00
Persistent=true
[Install]
WantedBy=timers.target
```

演练：在非生产或停机窗口 restore 到临时库，确认能登录；把成功日期记在运维笔记即可，不必把备份文件提交进仓库。

请求排障：响应头 `X-Request-ID` 与 journal / 平台日志同一编号。前端白屏会 `POST /api/client-errors`（需登录，限流），写入运行时日志。用户等待时间看管理端「用户等待」（`POST /api/client-rum`）。何时该打 logger 见 [`logging.md`](logging.md)。

## Minecraft / Pelican

圈子只有 Pelican 里那一台服。战鸽不另开 Java。在管理端「集成密钥」填 Panel 根地址、Client API Token（需 files + power）、Server UUID，以及 RCON 地址/端口/密码（服内自行 `enable-rcon`，不要对公网开放）。首次把 Egg 启动改成 `bash zhange/boot.sh <原来的 java 命令>`（示例见页面提示）。写操作走 Pelican Client API，与网页同一入口；在线人数是对公开端口的 status ping，TPS/MSPT 走 RCON。模组版本钉死，不会每次开服拉 latest。
