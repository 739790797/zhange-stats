# 工程约定

本文件集中记录跨层架构与平台集成中仍有效的项目约束。数据库、安全、日志、目录、上游仓与部署主题已有专门文档，相关细节以链接目标为权威；本文件只补充跨域实现边界及未由其他文档承载的规则。

## 权威主题文档

| 主题 | 权威来源 |
|---|---|
| 数据库模型、迁移与表结构 | [`database.md`](database.md)、[`backend/alembic/README.md`](../backend/alembic/README.md) |
| 安全、鉴权、文件管理、上传、跨源与房间权限 | [`security.md`](security.md) |
| Python 运行日志 | [`logging.md`](logging.md) |
| 代码分包与运行时目录 | [`directory-layout.md`](directory-layout.md)、[`data/README.md`](../data/README.md) |
| 前端路由权限 | [`frontend/README.md`](../frontend/README.md) |
| 开发环境与 CI 质量门 | [`develop.md`](develop.md) |
| 安装、运行、配置和发版 | [`deploy.md`](deploy.md) |

修改行为时先确认权威文档与实际代码一致；项目事实变化时，在同一改动里更新权威文档，不在多个位置复制容易漂移的长规范。

## 后端分层与 API 契约

- `backend/app/api/` 负责 HTTP 入参、依赖、状态码与序列化；业务编排放在按域组织的 `services/`，路由不得直接编排第三方上游 HTTP。
- 新平台进入 `services/<platform>/`，上游会话/认证写 `client.py`，签到查询/执行写 `attendance.py`，按需要拆分 box、calendar 或 raw pipeline；新逻辑不再持续膨胀旧的 `*_client.py`。
- 签到统一走 `checkin.orchestrator` + `CheckinPlatformAdapter` + `checkin.registry.ADAPTERS`；按项目现有平台接入 prefs、Bind/Log/Alembic、API status builder 与 scheduler wrapper。不要复制整份签到编排或把某个平台的渠道语义塞进全局 orchestrator。
- Adapter 的缓存补查、短时 cred/session 缓存、鉴权失败重试、`STATUS_UNKNOWN` 等能力按需留在具体 Adapter/平台服务层；不要为了单个平台把可选 hook 提升成所有平台都必须实现的全局流程。
- 复用 `app.core.timeutil` 的北京墙钟、`app.core.http_client.http_request` 的进程级 HTTP client、`crypto_secret` 的 Fernet 能力，以及既有路径/缓存/文件安全帮助函数；不要每次请求新建独立 HTTP client 或以当前工作目录猜运行时路径。
- 安装根配置的权威来源是 `config/*.json`；运行时数据、上传、缓存和临时目录遵守 [`develop.md`](develop.md) 与 [`data/README.md`](../data/README.md)。改 `scripts/config.example/` 字段时递增该文件 `_version`，并验证配置同步。
- 扫码/短时 KV/限流等使用项目共享存储能力；多实例必须共享 Redis；目前产品按单 `app` 副本设计。用户附件使用 `services/user_files/`，管理端文件管理遵循 [`security.md`](security.md)。
- 数据库结构变更必须加 Alembic migration 并同步 `docs/database.md`；新 migration 需兼容 SQLite 与 MySQL/MariaDB。不要在启动时绕过迁移改表。DDL 方言、`sa.JSON()`、`LongText` 等细节以 [`backend/alembic/README.md`](../backend/alembic/README.md) 为准。
- 后端契约变化后，在 `frontend/` 执行 `npm run export:openapi && npm run gen:api`，检查并提交 `frontend/src/api/generated/` 文件。不能只改手写前端类型冒充契约。

## 前端结构、请求与路由

- `pages/` 放路由页，`components/` 放可复用 UI；平台组件放 `components/<platform>/`，攻略放 `components/guides/`。源码静态资源放 `src/data/`，运行时数据在仓库根 `data/`，不要往 `frontend/data/` 写。
- 后端请求集中在 `frontend/src/api/*Api.ts`，统一使用 `@/api/http` 的共享 client；必要时由 `client.ts` 再导出。页面/组件不直连 axios 或裸 `fetch` 调本后端；上传、公开 `/health` 探测等特例必须有紧邻代码的说明。
- 用户可见失败文案用 `apiError`；不要在页面复制大型 response interface 或自行拆 `response.data.detail`。优先从 `@/api/generated/schema` 的 `components` 派生类型；仅当 OpenAPI 尚无 schema 时才新增手写 interface。
- 服务器状态放 TanStack Query，不把服务端列表移进 Zustand。路由页使用 `React.lazy`，由 `Suspense` 与 `RouteErrorBoundary` 包裹；不要将所有页面静态引入 `App.tsx`。平台 Tabs 保持既有非活动页卸载语义，盒子/兑换/养成重面板按需 lazy。
- 权限与公开路由以 [`frontend/README.md`](../frontend/README.md) 为准；新增公开功能仍由 API 权限/平台功能开关控制，不得为了访客 UI 暴露一份更宽的认证态接口。

## 前端复用组件与用户体验

- 新签到页/内容使用 `CheckinPageTemplate`；兑换页使用 `ExchangePageTemplate` + `ExchangeGoodsCard`；平台页使用 `PlatformFeatureTabsPage`；签到日历用 `AttendanceCalendarButton`；盒子/raw 面板先用 `BoxPanelChrome`；扫码绑定优先 `useQrBindSession`（表单按现有模板）；认证未登录页用 `AuthGuestShell`；管理子页放入 `AdminHubLayout`，不要再往侧栏堆叶子菜单。
- `PlatformFeatureTabsPage` 保持 `destroyInactiveTabPane`；平台子面板按现有模式 lazy。多角色对比板等例外先参照同域已存在实现，不为了套外壳改变其数据语义。
- 兑换相关页签与任务配置统一称“兑换”，面板标题用“兑换商城”；货币名只在余额/消耗文案中出现。
- 签到 status 前端必须显式把 `force: true | false` 放进 query，不可用 `...(force ? { force: true } : {})` 省略；`fetch*Status` 默认 `force=true` 对齐用户展示路径。调度读取 logs 通常走 service 层；如走 HTTP，显式传 `force=false`。盒子、日历、rogue 等 raw 接口通常默认 `force=false`，调用方显式传值以避免依赖默认。
- 站点统一 Ant Design 5 与 `antdAppTheme`；塔科夫暗色主题只在 `TarkovGuideShell` 的一层 `TarkovThemed` 中启用，详情页不再套第二层。不要引入第二套 UI 库、给主色写死 `#1a2332` 或把塔科夫专属主题扩散到主应用。
- 动效沿用项目 CSS（`app-motion-page` / `app-motion-in`）、Ant Design 内建动画与 `MotionIn`；尊重系统减少动态效果设置，不另引入 AutoAnimate/Motion 等动画库。
- 主要 CTA 使用 `type="primary"`，一个操作区保持一致尺寸；次要/取消/刷新用默认按钮，表格行/工具条用小号 link 或默认按钮，图标按钮用小号 text；破坏性操作须 `danger` 并二次确认。不要显式写默认 `size="middle"`、同一操作区混用 large/small，或用业务页原生 `<button>` 冒充主操作。
- 主内容区维持键盘可达的跳转链接、明确 `main`/导航标签和换页后的焦点行为；标题与页面切换使用项目现有文档标题、回顶和错误边界能力。新增焦点交互不可只支持鼠标。
- Modal 高度与窄屏宽度由全局 CSS 约束；不要在业务代码写死 `height`、`maxHeight: 720` 或 `72vh`。近全屏弹窗使用 `100dvh` 约束并让正文按需滚动，内容未溢出视口时不要制造滚动条。
- 例外保持局部：QQ 官方登录图、塔科夫模块、Minecraft 向导和雨中冒险 2 攻略壳的专用控件；酒馆编辑器可使用 TipTap 但工具栏仍用 Ant Design，公式渲染使用 KaTeX/LaTeX 与现有识别流程，不另加编辑器/公式编辑器主题。塔科夫滚动条统一走 `tarkovScrollbar.css`，不要在模块 CSS 复制原生滚动条规则。

## 签到、盒子与平台 raw 缓存

### 数据读取与签到展示

- 养成盒、图鉴旁路 raw、日历等可跨日缓存的数据：原始上游响应落库，`parse_*(raw)` 保持纯函数；普通访问读库，无记录或明确 `force` 时才回源。回源失败且有旧 raw 时可降级返回 stale 数据并标记状态。
- 签到状态/奖励不同于盒子缓存：用户打开签到展示页时始终向官方查询，不可因今日日志存在而短路；查询或签到后按角色、日期 upsert `*_checkin_logs`。定时任务可以利用今日成功日志跳过执行，但执行记录不是用户签到页面展示模型。
- `GET .../status` 展示路径默认必须回源；不要把签到状态写回 bind 的 `last_checkin_*` 摘要字段。`source` 可供内部排障，但不能成为用户“上次执行/已执行”叙事。
- 仅可信的已签结果展示今日奖励；结果不确定时用 `unknown`，不能伪装成未签或 pending。空奖励不得覆盖已有的更丰富奖励。

### 森空岛渠道与凭证

- 方舟 `channelMasterId=1` 为官服，`2` 为 B 服；B 服 attendance `gameId` 不得回退到官服 `1`。
- 官服 GET records 可作为可信查询；already/请勿重复签到后可按现有规则 GET 补今日 awards。B 服 GET records 为空不能判定未签，应为待确认；B 服只信 POST awards，禁止 already 后再 GET 补奖。日历 records 为空且无显式 claimed 时也不能推断全部未签。
- `skland_session_cache` 只缓存 cred/sign_token，TTL 约 20 分钟；绑定/解绑时失效。鉴权失败按森空岛流程 invalidate、换票并仅重试一次。扫码状态与 cred 使用共享 ephemeral store；多实例必须共享 Redis。
- 改渠道、补奖、cred 或 Adapter 行为时，分别测试官服/B 服分支；优先扩展 `backend/tests/test_skland_*` 与奖励择优回归测试，不顺手改变另一渠道语义。

## 上游仓、图鉴 raw 与游戏数据

- 安装根 `data/repos/` 中登记的资源仓由 `backend/app/services/upstream_repos.py` 统一管理，并由任务浅克隆/更新；普通读请求只解析本地登记仓，不按请求运行 Git，也不直接逐文件请求 raw URL。缺仓时用统一提示，引导管理员前往任务配置页手动同步。资源仓、时间、备份与文件管理以 [`data/README.md`](../data/README.md) 和 [`deploy.md`](deploy.md) 为准。
- 涉及仓生命周期、同步错误、资源解析的 pytest 必须使用本地 fixture、临时目录和注入的 Git runner；不得访问 GitHub/真实服务或执行 Git。更新失败要保留最后一份可用 checkout/raw。
- 通用图鉴复用 `GuideRawPipeline`：每份上游文件一行 raw 记录；先保存被接受的原始来源，再纯函数解析；压缩、冷启动和失败不覆盖规则沿用已有实现。不要另造重复 raw 表/压缩管道，也不要把解析结果当上游权威。
- 雨中冒险 2 的图鉴源为 `riskofrain2.wiki.gg` 同步原文；整份原文以同格式送译并写入 Weblate。展示只解析 `zh-Hans/` 中审核通过且指纹匹配的完整译文；无可信译文就不展示译文。不得现场回源其他图鉴 API、拆碎字符串翻译或用 SteamCMD 更新游戏。测试使用 dump/fixture。
- 塔科夫图鉴回源只读 `json.tarkov.dev` 的 `/regular/` 与 `/pve/` dump；每张 `tarkov_*_raws` 表对应一份来源文件，缺少的 dump 字段就视为不存在，不以 GraphQL 补齐。新标点从 `maps` raw 投影。历史 GraphQL split 信封仅为旧 raw 行兼容，不能扩展成新回源路径。
- 塔科夫 overlay 从已登记的本地 `data/repos/tarkov-data-overlay/dist/overlay.json` 在内存合并；不要把浏览器/raw URL 或额外 GraphQL 当作来源，也不要再落一份合并后的权威表。地图 SVG/瓦片、格仓轮廓属于展示资源，不是图鉴 API。
- 塔科夫工作台预览以 dump 枪图为底板，按槽位选择配件；缺少整枪坐标不意味着可把出图服务改成数据权威。image-gen 代理默认关闭，只有显式配置 `TARKOV_WORKBENCH_IMAGE_GEN=true` 才可启用。社区配装只 GET EFTForge 公开列表并投影为 dump 可装部件；不代投票/评论、不热链社区图片、不把其作为图鉴源，除短时 KV 外不持久化。枪匠约束来自 tasks dump 的 `buildWeapon`/`buildAttributes`，不 vendor 社区 JSON；工作台测试不得访问真实上游。
- 终末地干员信息和“烟火生缘”客栈准备求解使用本地 EndfieldData；客栈不要求森空岛绑定或养成盒凭证，厨师从 `InnCharTable` 过滤，菜单缺口明确展示。没有来源的公式或信息不估算、不编造。

## 战鸽助手边界

- 桌面助手 WebView 使用站点同源地址；嵌入态按嵌入标记隐藏站点侧栏，浏览器直接打开不隐藏。生产登录不能依赖 iframe、开发 localhost 或 Tauri 自定义源的跨站 Cookie；QQ/Steam 回跳仍落在站点地址。
- 游戏目录截图/日志通过本地文件桥读取；解析留在站点现有逻辑。战局使用既有摘要 API，房间定位只传既定数字坐标，截图只读文件名，不上传原图；不得新增接收原始日志或定位原图的接口。
- 助手不得重写截图文件名/坐标和日志解析。Cookie、CSRF、CORS 等权威安全细节见 [`security.md`](security.md)。

## 测试与成对更新

- 规则在哪层实现就优先在哪层测：后端测 service 解析、策略、权限/安全与 OpenAPI 不变量；前端测展示文案、格式化等纯函数。不要重复断言后端已覆盖的 payload 投影/slug 规范化/奖励择优。
- 不为整页组件随意引入 jsdom 测试；不使用真实 MySQL、同步 `TestClient` lifespan 或真实上游网络来验证普通单测。根据项目 fixture 隔离依赖，跨层只测各层差异。
- 签到渠道、Adapter、`force`、路径/密钥、日志抑制、外部数据回退等行为变化先找相邻回归测试并补差量；不要为了新平台复制已有公共行为的空壳测试。
- 必须同步的产物：API schema 变化生成 OpenAPI；表结构变更增加 migration 并更新 `docs/database.md`；配置模板字段变更递增 `_version` 并跑配置同步测试；附件走 `user_files` 并保持 API `serial` 契约；生产行为变化复核 [`security.md`](security.md)/[`deploy.md`](deploy.md)；日志变更对照 [`logging.md`](logging.md)。
- 验证范围与结果报告遵循 [`agent-guide.md`](agent-guide.md) 与 [`develop.md`](develop.md)，区分定向测试、全量质量门、环境/基线失败。