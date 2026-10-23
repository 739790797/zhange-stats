---
name: zhange-frontend-feature
description: 为战鸽数据新增、重构或视觉调整 React 页面、路由、组件与交互时使用；保持 feature-first 归属、路由/API/URL/数据语义，并完成相应前端验收。纯后端任务不使用；API 契约变化需配合 zhange-api-change。
---

# Zhange Frontend Feature

## 必要步骤

1. 阅读 [Agent 工作流程](../../../docs/agent-guide.md)、[工程约定](../../../docs/engineering-guidelines.md) 和[前端架构](../../../docs/frontend-architecture.md)；检查 `git status`、相关 diff、现有路由、页面、API、测试与运行表现，保留不相关改动。
2. 明确本次页面/能力范围和验收项。先记录需要保持的路由与权限、URL 查询参数、搜索/筛选行为、服务端状态、数据映射、本地化、加载/错误/空状态和来源归属；不要把视觉重做悄悄扩大成业务或契约变更。若任务属于目录迁移，不得顺带改视觉、文案、路由或请求语义；用户同时明确要求这些变化时，将其作为独立范围和验收项处理。
3. 遵守 `app → features → shared` 所有权与依赖方向。页面、业务组件、状态和 API client 放在所属 feature；跨域复用只走公开边界；服务端状态使用 TanStack Query，业务请求遵循项目共享 transport。不要沿用已迁移的旧目录路径或把业务实现塞进 `app/`。
4. 保持内容与数据来源可信：沿用现有类型、动态映射、翻译批准/回退和 attribution；缺少数据或译文时不要编造。遵循 Ant Design 与项目已有 token、资源和 feature 样式，不为视觉统一而改动无关页面。
5. 用户明确要求视觉设计/改版时，可使用已安装的上游 `frontend-design` 提供审美方向；结合页面真实主题和内容作有辨识度的设计。若用户已给设计自由度，不必等待 mockup；但外部 Skill 的通用审美建议不能覆盖项目规范、可读性、响应式、键盘焦点与 reduced-motion 需求。
6. 按改动层选择最近的 Vitest 测试；遵循工程约定与[开发/CI 质量门](../../../docs/develop.md)，不要为文档或纯样式改动无故运行无关后端测试。用户可见交互/视觉改动在可用时检查真实运行页面、受影响状态、控制台与窄屏布局；截图或源码 diff 不能代替实际页面验收。
   - 若使用上游 `webapp-testing`，仅对本地可信开发服务做浏览器检查；不将它替代 Vitest，不自动为产品安装 Playwright 依赖或运行生产站点。安装 Skill 本身不保证 Python Playwright 包和浏览器二进制可用；先确认当前解释器与浏览器运行时，缺少时使用已有浏览器/MCP 工具或如实报告未运行，不擅自改项目依赖。
   - 不要机械套用上游的全局 `networkidle` 等待示例：本项目部分页面有 TanStack Query 定时刷新或 WebSocket；优先等待目标路由的可见内容/具体请求信号，并设置有界超时，避免任意固定 sleep。
   - 上游 `with_server.py` 会以 shell 启动用户提供的服务命令，只尝试终止启动器进程，未必能清理嵌套子进程。使用前检查参数/脚本，只传入项目文档定义的开发命令；已有服务在运行时优先复用，不要启动重复服务或误杀现有进程。
7. 若触及 FastAPI/OpenAPI、前端 API 类型或跨栈行为，同时执行 [zhange-api-change](../zhange-api-change/SKILL.md)；若修改上游资源同步、raw 缓存或解析，执行 [zhange-upstream-data-change](../zhange-upstream-data-change/SKILL.md)；按需使用 [zhange-release-validation](../zhange-release-validation/SKILL.md)。结束前复核完整 diff、链接与 `git diff --check`，准确报告实际运行和未运行的检查。

## 权威文档

- [前端 Feature-first 架构](../../../docs/frontend-architecture.md)
- [工程约定](../../../docs/engineering-guidelines.md)
- [Agent 工作流程](../../../docs/agent-guide.md)
- [开发与 CI 质量门](../../../docs/develop.md)
- [Agent Skills 索引及上游版本](../../../docs/agent-skills.md)
