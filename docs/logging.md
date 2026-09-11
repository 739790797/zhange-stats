# 运行时日志规范

给排障用的 Python 日志（管理端「平台日志」）。**不是** `job_runs`、各平台 `*_checkin_logs`、塔科夫战局摘要：那些是业务落库，签到结果更不要当成「执行记录」展示给用户。

改代码时 Agent 看 [`.cursor/rules/logging.mdc`](../.cursor/rules/logging.mdc)；本文是人读全文。管道实现：`app.core.biz_logging`、`runtime_log_buffer`、`log_persistence`、`request_log_middleware`。

## 记到哪里

`logger.info` / `warning` / `exception` 默认同时进：

| 去处 | 位置 | 说明 |
|------|------|------|
| 内存环缓冲 | 约 5000 条 | 重启丢失；「清空缓冲」只清这里 |
| JSONL 文件 | `data/runtime/logs/app.jsonl` | 按大小轮转（默认 50MB × 5） |
| 进程 stdout | systemd journal | uvicorn 照常带 |

每条自动带：级别、logger 名、从 logger 名推出的 **biz**、`log_context`（如 `request_id`、`job`、`member_id`）。北京墙钟时间。

配置：`APP_LOG_LEVEL`（默认 `INFO`）、`APP_LOG_RING_CAPACITY`、`APP_LOG_FILE`（默认开）、`APP_LOG_FILE_MAX_MB`、`APP_LOG_FILE_BACKUP_COUNT`。`DEBUG` 才会放行 SQLAlchemy SQL。

## HTTP 中间件已经记的

`zhange.http` 管访问日志，业务里不要再抄「这个 GET 成功了」。

**不记：** `/health`、静态资源、头像、运行环境 / 平台日志自己的轮询、`POST /api/client-rum`（浏览器 RUM 批量上报）。

**必记：** 非 GET（写操作）。

**GET：** 仅状态 ≥400 或耗时 ≥200ms。又快又成功的读请求保持静默。

`X-Request-ID` 写入上下文并回响应头；对一次失败的 API 用这个 ID 在平台日志里搜。前端白屏走 `POST /api/client-errors`（`zhange.client` WARNING），不要另上一套 Sentry。用户等待时间走浏览器 RUM：`POST /api/client-rum` 落 `rum_samples`，管理端「运行维护 → 用户等待」看 p50/p95，**不要**把每条耗时打进 INFO。

调度任务用 `wrap_scheduled_job`：统一 `scheduled job begin/done/failed`，不要每个 job 再包一层同样的 begin/done。

## 级别

| 级别 | 何时 |
|------|------|
| **DEBUG** | 默认看不见。循环内细节、逐文件成功、可预期的「这次跳过」、重复的同一故障 |
| **INFO** | 里程碑：启动步骤、任务 begin/done 与汇总、同步开始/结束条数、Redis 连上 |
| **WARNING** | 带伤继续：降级内存、上游失败但有旧数据、SMTP 未配、配置缺失、前端白屏、CSP 违规。同一故障不要每 15 秒再打一遍（用 `log_until_change`） |
| **ERROR** / `exception` | 不该发生的失败，且要堆栈时用 `logger.exception` |

一句话：**INFO 是发生了什么；WARNING 是带伤在跑；ERROR 是这次挂了；成功的读请求默认闭嘴。**

## 该发

- 进程生命周期（`zhange.startup` 各步、关闭调度器）
- 任务/同步 **一条开始、一条汇总**（成功/失败/跳过计数），不要每个成员、每个 app_id、每个 dump 文件一条 INFO
- 降级发生的 **第一次**（Redis 不可用、RCON 连不上）
- 安全与运维：弱口令检查、迁移失败、**更新 pip/migrate 的逐行输出**（偶发运维流，与签到循环不同）

## 不该发

- 成功且快的 GET；平台日志 / 运行环境 / `/health` 的轮询；RUM 上报
- 循环里「处理了第 N 个」——签到一轮上百人会把环缓冲顶满
- 密钥、Cookie、JWT、房间密码、验证码明文（生产 `ALLOW_EMAIL_CODE_LOG` 启动硬拒绝）
- 上游整段 JSON、含 token 的响应体；QQ 用户信息失败只打 `ret`/`msg`
- 给用户看的签到「上次执行」叙事（那是库表，不是 logger）
- `print()`（验证码本地调试除外，且不得进生产）

高频探活（RCON、三狗轮询、Redis 调用失败）：用 `log_until_change`。同一 `key` + 同一格式化消息只打一次 WARNING，之后 DEBUG；恢复成功后 `clear_log_until_change(key)`，下次失败再 WARNING。

## logger 名

- 模块内默认 `logging.getLogger(__name__)`，biz 从包路径推（`app.services.skland.checkin` → `skland.checkin`）
- 横切用稳定名：`zhange.http` / `zhange.scheduler` / `zhange.startup` / `zhange.client` / `zhange.csp` / `zhange.ocr` / `zhange.migrate`
- 需要筛成员或任务时：`with log_context(platform="skland", member_id=bind.member_id, job="checkin")`

## 前端

不要 `console.log` 业务。用户可见失败用 `apiError`。渲染崩溃：`RouteErrorBoundary` 可 `console.error`，同时 `POST /api/client-errors`。接口转圈与第三方图等待走 `POST /api/client-rum`（批量、失败静默）。不要把生产堆栈默认送到第三方。

## 怎么看

管理端 **运行维护 → 平台日志**：筛级别 / logger / biz / 关键字。默认 INFO+。依赖是否可用看 **运行维护 → 运行环境**。用户侧等待（接口转圈 / 第三方图）看 **运行维护 → 用户等待**，不要把 RUM 样本打进平台日志。

磁盘：`data/runtime/logs/app.jsonl`。对一次请求：浏览器响应头 `X-Request-ID` 与日志 `context` 同一编号。
