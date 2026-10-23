# 雨中冒险 2 列表规则与新页面模板

本文记录 ROR2 列表共用的来源排序、名称排序、分组例外和 DLC 主图角标约定。实现位于 `frontend/src/features/guides/ror2/`；这些游戏规则属于 ROR2 feature，不提升到全站 `shared/`。

## 默认排序

来源顺序复用顶部栏：本体 → 虚空幸存者（SotV）→ 风暴探寻者（SotS）→ 合金意念（AC）→ 神圣观念（HC）；未知来源排在已知来源之后，并按来源 ID 稳定排序。名称排序优先使用有审核译文时的中文名拼音；没有可用译文时回退上游原名，不自行补译。

| 页面 | 默认顺序 | 说明 |
|---|---|---|
| 物品 | 品质 → 来源 → 中文拼音 | 品质沿用筛选器既有顺序；保留列头排序交互。 |
| 幸存者 | 本体/DLC 来源 → Wiki 幸存者名单顺序 | 有意保留游戏 roster 顺序，不改成拼音。 |
| 怪物 | 怪物类型组 → 组内来源 → 中文拼音 | 分组顺序按 Wiki。 |
| 成就 | 成就类别组 → 组内来源 → 中文拼音 | 无主图，DLC 标记放成就名称旁。 |
| 可交互物 | Wiki 分类组 → 组内来源 → 中文拼音 | 分类组顺序按 Wiki。 |
| 神器 | 神器组 → 来源 → 中文拼音 | 单组图鉴。 |
| 无人机 | 来源类型组 → 组内中文拼音 | API 暂无来源字段；只排序名称，不推测本体/DLC。 |
| 环境 | 关卡组和 Wiki 既有顺序 | 不做拼音重排。 |
| 纽特祭坛 | 关卡既有顺序 | 不做拼音重排。 |
| Unreleased | Wiki 小节和条目既有顺序 | 不做拼音重排。 |

`sortRor2Rows`、`ror2ExpansionOrder` 在 `model/ror2List.ts`；物品/幸存者特有顺序继续由 `model/ror2Home.ts` 管理。目录页策略集中在 `ROR2_DIRECTORY_LIST_RULES`，页面组件不应另造一套比较逻辑。

## 列表图片来源角标

- 有可用主图且来源是 DLC：使用 `Ror2ListMedia`，在右下角叠加来源图标。
- 没有主图或主图加载失败：用 `Ror2ListDlcMark` 在名称旁标记，避免角标悬在空占位图上。
- 无主图的成就表格继续用名称旁标记；解锁奖励图不是成就主图，不能贴成就的 DLC 角标。
- 角标框只用于列表；详情页与导航弹窗维持各自展示。只有数据契约明确提供来源时才标记 DLC。
- 当前 `Ror2DroneResponse` 没有 `expansion` 字段，因此无人机不加 DLC 标记；不能根据图片或类别猜来源。

## 新建目录列表页

优先复用 `components/Ror2DirectoryView.tsx`：它统一数据载入、Wiki 结构、分组筛选、URL 查询参数、搜索、计数、空态/错误态和列表卡片。新增页面时：

1. 在 `ROR2_SECTIONS` 或 `ROR2_EXTRA_PAGES` 声明页面 ID、标题、路径和计数单位。
2. 在 `ROR2_DIRECTORY_LIST_RULES` 为新 ID 声明稳定的 `groupOrder`、组内 `rowOrder`（`source-name`、`name` 或 `canonical`）和可选 Wiki 文章 ID。完整 `Record` 会在添加新目录 ID 时要求同步补策略。
3. 在 `ror2SectionRows`（或 unreleased 专用映射）实现数据投影，并透传原始 `expansion` 字段；来源未知就保持未知。
4. 在 `app/App.tsx` 注册路由；首页入口是否自动出现由页面是否属于 `ROR2_SECTIONS` 决定。
5. 在相邻模型测试中覆盖分组顺序、组内排序或 canonical 顺序；有主图的卡片使用 `Ror2ListMedia`。

新数据若要参与来源排序/角标，先确认 API/数据源确实提供可信 `expansion`；跨栈契约变更遵循工程约定并生成 OpenAPI 类型。
