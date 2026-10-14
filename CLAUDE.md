@AGENTS.md

# 战鸽数据 · Claude 委派约定

> 只写「怎么派活」一件事。约定、禁止清单、PR 自检全在 `AGENTS.md`（已由首行导入）与 `.cursor/rules/`，此处不重复。
> 与治理方案一致：索引短、专项深、一条规则一个关注点（`docs/agent-governance-plan.md`）。

## 为什么有这份文件

`AGENTS.md` 只是 Claude 的**兜底**：项目里一旦存在 `CLAUDE.md`，`AGENTS.md` 默认就不再加载。首行 `@AGENTS.md` 是真导入，确保约定不会因本文件出现而静默失效。本文件只补委派缺口。

## 模型与强度的硬事实

- **模型解析顺序（现行）**：单次调用的 `model` 参数 → agent frontmatter `model` → `CLAUDE_CODE_SUBAGENT_MODEL` 环境变量 → 主会话模型。
- **不显式指定 = 继承主会话模型。** 主会话跑 Opus 时，不 pin 的 subagent 也按 Opus 计费。
- **`effort` 只能写在 agent frontmatter 里**，没有单次调用的 effort 参数。合法值 `low` / `medium` / `high` / `xhigh` / `max`；具体档位受模型支持情况限制。
- frontmatter 字段名写错会**静默失效**，不报错。改动后请用 `/model` 或 subagent 日志核对，别只看文件写没写。
- agent 定义放在 `.claude/agents/`，**已 gitignore、不入库**（桌面端不加载自定义类型，只对 CLI 有用）。因此这些文件只存在于本机：clone 仓库的人不会有它们，下文提到的 `zhange-*` 类型名对别人是空引用。

## 分工

主会话（Opus，强）保留判断类工作：

- 根因定位、跨文件推理、架构与 Alembic 迁移决策、tradeoff 取舍
- 任务拆解、派发、**验收**
- 任何依赖本轮对话历史的活（subagent 是全新上下文，看不到之前聊过什么）

派出 subagent 的活：

- 只读扇出检索、文件发现、总结既有行为
- **文件集互不相交**的并行批量修改
- 文档清扫、`export:openapi` 后的重复核对、测试跑批

以上只是默认倾向，遇到下面情况仍由主会话直接做：单文件但要吃对话上下文的改动、琐碎小改（规划开销会超过收益）、以及任何尚未定清规格的活。

## 强度与模型分层

| 活的类型 | agent 类型 | model | effort |
|---|---|---|---|
| 只读检索、文件发现、总结 | `zhange-quick-search` | haiku | low |
| 常规实现、补测试、文档清扫、批量改写 | `zhange-impl` | sonnet | medium |
| 根因排查、架构评审、安全 / 正确性审查 | 主会话直接做（必要时 `zhange-deep-review`） | opus | high |

约定：

- 默认副手用 `zhange-impl`（sonnet / medium）；纯检索用 `zhange-quick-search`（haiku / low）
- **不降级判断类工作。** 根因、架构、安全审查留在主会话；确需并行时用 `zhange-deep-review`（opus / high）
- 不用 `xhigh` / `max` 做常态执行——留给真正难的判断
- 派发时在说明里带上【类型 / model / effort】，便于事后核对

## 派发要求

派之前先定**验收标准**，并写进 prompt：

- 产物是什么（文件路径、可跑的门禁命令）
- 什么算过（`npm run lint` / `pytest -q` / `tsc --noEmit` 绿，或指定测试通过）
- 边界（能改哪些文件；其余一律不动）

回收时**检查产物，不认「done」**：看文件真的存在、diff 真的落在约定范围内、门禁真的绿。与 `AGENTS.md` 的 PR 自检一致——改 API 有 `generated/` diff，改模型有 Alembic + `docs/database.md`。

给 subagent 的 prompt 必须自包含：它看不到本会话历史，所以 `AGENTS.md` / `.cursor/rules/` 里的相关约束要复述进去，别指望它自己知道。

## 何时不要派

- 任务小到规划开销超过收益（社区实测：弱模型执行会多花约 50% 回合、48% 工具调用，规格不细就返工）
- 需要对话上下文才能判断的活
- 多个 agent 会改同一批文件——并行前必须确认文件集不重叠
- 尚未定清规格——先把规格定死；跨边界的决定要在 brief 里钉死，否则执行者会各自发明互斥的做法

## 已知失效点

**桌面端实测（2026-10-14）：`.claude/agents/` 的自定义类型未被注册。** 派 `zhange-quick-search` 报错——

```
Agent type 'zhange-quick-search' not found.
Available agents: claude, claude-code-guide, Explore, general-purpose, Plan, statusline-setup
```

即只有内置类型（对应 #77057）。所以本表在**桌面端 agent 模式暂时降级为「建议」**：

- 退回内置 `Explore` / `general-purpose`，在**单次调用里 pin `model`**——这个参数有效。
- **`effort` 无法在单次调用里指定**，只能靠 agent frontmatter。桌面端拿不到自定义类型时，就吃不到分档强度——这是本方案在桌面端的真实上限，别以为写了就一定生效。
- 注册表在会话启动时缓存（#68043），新会话可能才认；CLI 侧用 `claude --agent zhange-impl` 可验证。要真用得先确认类型出现了，再谈分档。

另外两个坑：

- frontmatter 的 `description` 含 ASCII `: ` 时，CRLF 工作树下可能解析失败并被**静默丢弃**（#82361）。本目录的 description 一律用引号包裹、且只用全角「：」，改动时保持这个写法。
- 贡献者若自行添加 `CLAUDE.local.md`，会把本文件与 `AGENTS.md` 一起顶掉（它也算 CLAUDE.md）。届时告知本人，不要往仓库里塞对策。
