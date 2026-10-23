# 前端 Feature-first 架构与目录约定

本文是 `frontend/src` 的权威目录归属规范。目录迁移只改变代码组织与导入路径，不改变用户可见行为、路由权限、请求语义或后端 API 契约。

## 目标结构

```text
frontend/src/
├── app/                         # 应用启动、路由组合、全局壳与应用级样式
│   ├── router/
│   ├── http/
│   ├── shell/
│   ├── styles/
│   ├── theme/
│   └── telemetry/               # 应用启动的遥测接线
├── features/
│   ├── home/                    # 首页/工作台
│   ├── auth/                    # 登录、注册、会话与初始化
│   ├── profile/                 # 个人资料、绑定与角色
│   ├── admin/                   # 管理页面、系统设置与运维
│   ├── daily/                   # 签到聚合与每日任务
│   ├── articles/                 # 酒馆文章与编辑
│   ├── legal/                   # 服务条款与隐私政策
│   ├── site/                    # 站点公开设置与备案信息
│   ├── platforms/
│   │   ├── shared/              # 平台域内可复用 UI、能力模型与流程
│   │   ├── steam/
│   │   ├── skland/              # 森空岛、明日方舟、终末地与干员信息
│   │   ├── exilium/
│   │   ├── kujiequ/
│   │   ├── mihoyo/
│   │   └── taygedo/
│   └── guides/
│       ├── shared/              # 攻略域内导航与共享页面部件
│       ├── minecraft/
│       ├── ror2/
│       └── tarkov/
└── shared/
    ├── api/                     # HTTP transport、错误基础设施与生成契约
    │   └── generated/           # OpenAPI 生成物，禁止手工修改
    ├── ui/                      # 与产品域无关的基础 UI
    ├── hooks/                   # 通用 React hooks
    ├── lib/                     # 通用纯函数与基础工具
    ├── assets/                  # 通用资源
    ├── styles/                  # 跨 feature 设计 token/基础样式
    └── locales/                 # 应用共享本地化
```

feature 内只创建实际需要的 `pages/`、`components/`、`api/`、`hooks/`、`model/`、`assets/`、`data/`、`styles/` 等目录；不为对称而创建空目录。

## 归属规则

1. **先判断业务所有权，再考虑复用次数。** 页面、业务组件、状态、领域逻辑、资源、数据和业务 API 客户端归拥有该能力的 feature；不能因为多个地方 import 就自动放进 `shared/`。
2. **跨 feature 复用业务 API 时复用 owner 的导出，不复制请求实现。** 调用方通过 owner feature 的公开 API 模块复用；若逻辑确实是全产品无领域的基础设施，才提升到 `shared/`。
3. **`shared/` 不依赖 `features/`。** `shared/api` 只放无业务归属的 HTTP transport/通用请求错误基础设施和 OpenAPI 生成契约；登录登出、平台缓存、攻略参数、遥测采集等业务集成由 owner feature 或 `app/` 装配。
4. **域内共享仍留在域内。** 多个平台共用的绑定/兑换/平台导航组件放 `features/platforms/shared/`；多类攻略共用的导航/页面部件放 `features/guides/shared/`，而不是全局 `shared/ui/`。
5. **`app/` 负责装配，不承接业务实现。** `app/main.tsx` 负责初始化与 provider 装配；`app/router/` 组合 feature 页面、路由、权限门禁、错误边界和懒加载；全局壳与全局 reset 放 `app/`。具体页面仍归 feature。
6. **样式和资源跟随拥有者。** 全局 reset/应用壳样式放 `app/styles/`；通用设计 token 放 `shared/styles/`；页面/组件专属 CSS、图片、字体和 JSON 数据与对应 feature 并置。
7. **类型跟随契约所有者。** 领域 API/types 放 owner feature；后端 OpenAPI 契约只从 `shared/api/generated/` 导入。生成文件由 `npm run export:openapi && npm run gen:api` 更新，不手改生成类型。
8. **测试靠近实现。** 纯函数测试与被测模块同目录；组件测试放组件域内。文件搬迁后同步更新测试路径，不借迁移改变测试行为或扩大测试环境。

## 导入方向

```text
app  ──可组合──> features/* ──可依赖基础设施──> shared/*
                         └──可通过公开 API 复用其他 feature 的 owner 导出
shared ──禁止──> features/* 或 app/*
```

依赖方向固定为 `app → features → shared`：feature 不得依赖 `app/`，`shared/` 不得依赖 `features/` 或 `app/`。feature 之间仅通过明确的公开边界复用（例如 `profile` 提供的角色选择 API、`admin` 拥有的集成配置 API）；避免导入其他 feature 的私有页面/组件内部实现。若多个同域 feature 需要 UI 或业务流程，优先放到该域的 `shared/` 子目录。app/router 通过组合或依赖注入向 feature 壳装配权限与错误边界，不由 feature 反向导入路由实现。

## 本项目边界示例

- `authStore` 属于 `features/auth/model/`；资料补全和角色成员选择属于 `features/profile/`。
- Arknights、Endfield、operator info 与 Skland API 同属 `features/platforms/skland/`。
- Tarkov 的页面、组件、逻辑、地图 JSON、API 客户端和字体均归 `features/guides/tarkov/`。
- 通用 HTTP transport 与 CSRF 基础工具位于 `shared/api/`；请求层不直接导入 auth、platform 或 guide feature。应用启动时由 app 装配各 owner 的拦截器/请求集成，保持既有行为。
- `features/site/` 拥有公开站点设置展示与 ICP 备案链接；管理端设置通过该 owner 的 API 复用，不复制客户端。

## 目录迁移约束

- 迁移期间允许临时兼容 facade，最终必须删除；生产代码、测试、脚本、CI 和文档不得继续引用已清理的旧层路径。
- 迁移是文件归属与导入路径调整；不得借机拆分大型页面、改视觉/文案、调整 route path/权限/懒加载或改变请求与缓存语义。
- 每批迁移后运行 `npm run lint`、全量/受影响 Vitest 测试和 `npm run build`；收尾核对 OpenAPI drift、旧路径引用、文档链接与 `git diff --check`。部分通过不得报告为全绿。
