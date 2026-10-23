# Agent Skills

本仓库使用标准 Agent Skills 目录结构。根 `AGENTS.md` 提供自动加载入口，项目级技能放在 [`.agents/skills/`](../.agents/skills/)；`docs/` 保存完整、权威的项目规则。

## 技能分类

| 类别 | 维护方 | 本仓库约定 |
|---|---|---|
| 项目专用 Skills | 本仓库 | 只描述触发条件、必做步骤、验收/停止条件与权威文档链接；流程细节由 `docs/` 维护，不在 `SKILL.md` 复制长规范 |
| 通用上游 Skills | 外部开源仓库 | 本仓库不 vendoring、不改写上游技能文件；以固定 commit checkout 或 Codex 用户级技能安装器接入，并记录来源、版本与许可 |

## 项目专用 Skills

| Skill | 触发场景 | 权威正文 |
|---|---|---|
| [`zhange-api-change`](../.agents/skills/zhange-api-change/SKILL.md) | FastAPI、OpenAPI、前端 API/types 或跨栈契约变更 | [`engineering-guidelines.md`](engineering-guidelines.md)、[`frontend/src/shared/api/generated/README.md`](../frontend/src/shared/api/generated/README.md) |
| [`zhange-upstream-data-change`](../.agents/skills/zhange-upstream-data-change/SKILL.md) | 上游仓、外部数据同步、raw 缓存、解析与刷新 | [`data/README.md`](../data/README.md)、[`engineering-guidelines.md`](engineering-guidelines.md) |
| [`zhange-release-validation`](../.agents/skills/zhange-release-validation/SKILL.md) | 测试选择、质量门、交付或发版验证 | [`agent-guide.md`](agent-guide.md)、[`develop.md`](develop.md)、[`deploy.md`](deploy.md) |
| [`zhange-frontend-feature`](../.agents/skills/zhange-frontend-feature/SKILL.md) | 战鸽数据 React 页面、路由、交互、组件或视觉变更 | [`frontend-architecture.md`](frontend-architecture.md)、[`engineering-guidelines.md`](engineering-guidelines.md)、[`develop.md`](develop.md) |

## 通用上游：Addy Osmani Agent Skills

- 来源：[`addyosmani/agent-skills`](https://github.com/addyosmani/agent-skills)，版本标签 [`0.6.13`](https://github.com/addyosmani/agent-skills/tree/0.6.13)
- 许可：[MIT](https://github.com/addyosmani/agent-skills/blob/0.6.13/LICENSE)（以固定版本 checkout 中的 `LICENSE` 为准）
- 项目采用版本：`0.6.13`
- 对应 commit：[`aeac41d4d005999432bb7312f7ff06383a91d59d`](https://github.com/addyosmani/agent-skills/commit/aeac41d4d005999432bb7312f7ff06383a91d59d)
- 上游包含 Codex 插件配置与共享 Skills；本仓库只记录版本与接入步骤，不复制或编辑其 Skill 文件。

### 从固定版本的本地 checkout 注册 Codex 插件

以下示例把上游仓克隆到用户目录，避免把上游代码带进本项目。将 `$HOME/agent-plugins/agent-skills` 换成自己希望长期保留的路径。用完整 commit 固定内容，不要直接安装浮动的 `main`。

```powershell
$pluginRoot = "$HOME/agent-plugins/agent-skills"
git clone https://github.com/addyosmani/agent-skills.git $pluginRoot
git -C $pluginRoot checkout --detach aeac41d4d005999432bb7312f7ff06383a91d59d
git -C $pluginRoot rev-parse HEAD  # 应输出上面的固定 commit

codex plugin marketplace add $pluginRoot
codex plugin list --available --marketplace agent-skills
codex plugin add agent-skills@agent-skills
```

插件安装器从已注册的本地 marketplace 读取清单；安装后按 Codex 提示重新加载/重启会话，再检查技能是否出现。若本机版本的插件 ID 与示例不同，以 `codex plugin list --available` 输出和该固定 checkout 的上游说明为准。

更新时先选定新的上游 tag 与 commit，检查许可/变更，更新本文版本和 commit，再切换本地 checkout 并重新注册/升级插件；不要为方便而复制上游技能到 `.agents/skills/`。

## 通用上游：Anthropic Agent Skills

- 来源：[`anthropics/skills`](https://github.com/anthropics/skills)
- 固定 commit：[`dbd4588f9e1033efb41dad4bef2f7947c8993d44`](https://github.com/anthropics/skills/commit/dbd4588f9e1033efb41dad4bef2f7947c8993d44)（2026-10-09）
- 许可：[`frontend-design`](https://github.com/anthropics/skills/blob/dbd4588f9e1033efb41dad4bef2f7947c8993d44/skills/frontend-design/LICENSE.txt) 与 [`webapp-testing`](https://github.com/anthropics/skills/blob/dbd4588f9e1033efb41dad4bef2f7947c8993d44/skills/webapp-testing/LICENSE.txt) 各自的 `LICENSE.txt` 均为 Apache-2.0；安装时保留许可文件。
- 本项目采用：`frontend-design` 与 `webapp-testing`。上游 Skill 文件安装到 Codex 用户级 `$CODEX_HOME/skills/`，不复制进本仓库，也不修改上游正文。

| 上游 Skill | 适用范围与项目边界 |
|---|---|
| [`frontend-design`](https://github.com/anthropics/skills/blob/dbd4588f9e1033efb41dad4bef2f7947c8993d44/skills/frontend-design/SKILL.md) | 只在新页面或明确的视觉改版任务使用；用真实产品主题形成视觉方向，不覆盖项目路由、数据映射、可读性、响应式和无障碍要求。 |
| [`webapp-testing`](https://github.com/anthropics/skills/blob/dbd4588f9e1033efb41dad4bef2f7947c8993d44/skills/webapp-testing/SKILL.md) | 用 Playwright 对本地页面做交互/渲染检查，补充而不替代 Vitest。Skill 安装不提供 Python Playwright 包或浏览器二进制，使用前确认本机运行时；对定时刷新/WebSocket 页面等待具体 UI 信号，不盲等全局 `networkidle`。其 `with_server.py` 以 shell 启动指定命令，并只尝试停止启动器进程；不要假设嵌套子进程树会被清理。先审阅脚本与参数，只使用本文档化的本地开发命令，不用于生产服务，也不重复启动/终止已有开发服务。项目开发端口及启动方式以 [`develop.md`](develop.md) 为准。 |

### 从固定 commit 安装到 Codex 用户级 Skills

以下使用 Codex 自带的 Skill Installer；若目标目录已存在，先核对版本，不要覆盖未知内容。默认安装位置是 `$CODEX_HOME/skills/`（未设置 `CODEX_HOME` 时为 `~/.codex/skills/`）。

```powershell
$codexHome = if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $HOME ".codex" }
$installer = Join-Path $codexHome "skills/.system/skill-installer/scripts/install-skill-from-github.py"
python $installer --repo anthropics/skills --ref dbd4588f9e1033efb41dad4bef2f7947c8993d44 --path skills/frontend-design skills/webapp-testing
```

安装后重新加载 Codex 会话，再确认 `frontend-design` 与 `webapp-testing` 可用。更新时先审阅新 commit、两个 Skill 的脚本及许可证，再更新本文 commit 并替换用户级安装；不要追踪浮动的 `main`。
