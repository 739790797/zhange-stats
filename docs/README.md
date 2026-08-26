# 战鸽数据 · 文档目录

仓库里全部 Markdown / Cursor 规则的**索引**。正文不复制。根 [`README.md`](../README.md) 只介绍产品功能。

## 为什么不全搬进 `docs/`

| 必须留在原位 | 原因 |
|---|---|
| 根 [`README.md`](../README.md) | GitHub / 克隆后的落地页（产品介绍） |
| 根 [`AGENTS.md`](../AGENTS.md) | Agent 总入口（Cursor / 其他工具默认读仓库根） |
| [`.cursor/rules/*.mdc`](../.cursor/rules/) | Cursor 按路径加载；`alwaysApply` 与 glob 只对这个目录生效 |
| 各子目录 `README.md` | 打开该目录就能看到「这是干什么的」 |

人找文档从本页进；Agent 改代码从 `AGENTS.md` → `.cursor/rules/`。

---

## 按角色怎么走

| 你要… | 先打开 |
|---|---|
| 了解产品做什么 | [`README.md`](../README.md) |
| 克隆后跑起来 | [`develop.md`](develop.md) |
| 上生产 / 一键更新 | [`deploy.md`](deploy.md) |
| 查某张表、改表 | [`database.md`](database.md) + [`backend/alembic/README.md`](../backend/alembic/README.md) |
| 安全 / JWT / Redis / 弱口令 | [`security.md`](security.md) |
| 改代码、加平台、改签到 | [`AGENTS.md`](../AGENTS.md) → [架构索引](../.cursor/rules/zhange-architecture.mdc) |
| 查目录该怎么分包 | [`directory-layout.md`](directory-layout.md) |
| 看约定是怎么定下来的 | [`agent-governance-plan.md`](agent-governance-plan.md)（已落地，归档备查） |

---

## 入口（仓库根）

### [`README.md`](../README.md)

产品介绍：账号、Steam、签到平台、塔科夫 / Minecraft、管理端。开发与部署不写在这里。

### [`AGENTS.md`](../AGENTS.md)

给 Agent / 开发者的工作入口：**改代码前必读列表、高频命令、禁止清单、PR 自检、CI**。细则链到 `.cursor/rules/` 与 `docs/`。

---

## 本目录（`docs/`）

| 文件 | 一句话 |
|---|---|
| [`develop.md`](develop.md) | 技术栈、Windows 本地开发、工程 / CI、目录树 |
| [`deploy.md`](deploy.md) | LXC 安装、管理端更新、部署形态、Minecraft / Pelican |
| [`database.md`](database.md) | 表结构总览（改模型必须同步本文） |
| [`security.md`](security.md) | JWT、弱口令、Redis、邮件验证码日志、密钥 |
| [`directory-layout.md`](directory-layout.md) | `var/` 与 services/components 分包映射（已落地） |
| [`agent-governance-plan.md`](agent-governance-plan.md) | 治理方案原文（已落地，归档） |

---

## Agent 规则（`.cursor/rules/`）

Cursor 规则，不是给人当手册从头读的。架构索引始终加载；其余按 glob 在改对应文件时带上。

| 文件 | 何时加载 | 一句话 |
|---|---|---|
| [`zhange-architecture.mdc`](../.cursor/rules/zhange-architecture.mdc) | 始终 | 各域「必须 / 禁止 / 去哪看」总表，细节不重复写 |
| [`platform-raw-cache.mdc`](../.cursor/rules/platform-raw-cache.mdc) | 签到/盒子/API | 盒子与旁路 raw **读库优先**；签到展示打开页始终 **force 回源** |
| [`skland-upstream.mdc`](../.cursor/rules/skland-upstream.mdc) | 森空岛相关 | 官服 / B 服渠道语义、补奖、`unknown`、cred 缓存 |
| [`db-schema-readme.mdc`](../.cursor/rules/db-schema-readme.mdc) | `models/`、迁移 | 改表必须 Alembic + 同步 `docs/database.md` |
| [`backend-conventions.mdc`](../.cursor/rules/backend-conventions.mdc) | `backend/app/` | `api/` 薄、`services/` 厚；新平台 Adapter + 注册表 |
| [`frontend-conventions.mdc`](../.cursor/rules/frontend-conventions.mdc) | `frontend/` | 签到/兑换/平台页套 Template；status **显式传** `force` |
| [`frontend-api-errors.mdc`](../.cursor/rules/frontend-api-errors.mdc) | 页面、组件、`api/` | 用户可见错误用 `apiError`；请求走域 `*Api.ts` |
| [`frontend-ui.mdc`](../.cursor/rules/frontend-ui.mdc) | 前端 ts/css | 只用 Ant Design 5 + `antdAppTheme` |
| [`testing.mdc`](../.cursor/rules/testing.mdc) | 测试与纯函数 | 规则在哪层实现就在哪层测 |
| [`directory-layout.mdc`](../.cursor/rules/directory-layout.mdc) | services/components | 新平台进子包；全文见 `directory-layout.md` |

---

## 就地 README（跟着代码走）

| 文件 | 一句话 |
|---|---|
| [`frontend/README.md`](../frontend/README.md) | 前端命令、目录要点、路由权限 |
| [`frontend/src/api/generated/README.md`](../frontend/src/api/generated/README.md) | OpenAPI 生成物：勿手改；改 API 后 `export:openapi && gen:api` |
| [`frontend/public/brand/README.md`](../frontend/public/brand/README.md) | 战鸽品牌 SVG 用途 |
| [`backend/alembic/README.md`](../backend/alembic/README.md) | 改表流程、幂等迁移、MariaDB 方言 |
| [`backend/local_dev/README.md`](../backend/local_dev/README.md) | 本地假 Steam 数据 CLI |
| [`var/README.md`](../var/README.md) | 运行时目录约定 |

---

## 不算文档、但常被当成文档的东西

| 位置 | 实际是 |
|---|---|
| `.env.example` | 环境变量清单与注释 |
| `VERSION` | 发版号；`main` 推送按它打 GitHub Release |
| `deploy/systemd/zhange-stats.service` | 生产 systemd 单元 |
| `scripts/install.sh` · `run_dev.bat` | 安装 / 本地热重载入口 |

贡献约定在 `AGENTS.md`，安全说明在 [`security.md`](security.md)。
