export const LEGAL_TERMS_PATH = "/legal/terms";
export const LEGAL_PRIVACY_PATH = "/legal/privacy";

export const ICP_BEIAN_NO = "浙ICP备2025147006号";
export const ICP_BEIAN_HREF = "https://beian.miit.gov.cn/";

export const TARKOV_PUBLIC_DISCLAIMER =
  "本站与 Battlestate Games 无关，不是官方工具，也不提供任何作弊功能。地图与物品数据来自社区 tarkov.dev。联机房间仅供队友协作勾任务与标点。";

export const RAID_ROOM_TITLE_POLICY =
  "房间名禁止违法、骚扰、歧视或广告内容。";

export type LegalDocId = "terms" | "privacy";

export type LegalDoc = {
  id: LegalDocId;
  title: string;
  updated: string;
  paragraphs: string[];
};

export const LEGAL_DOCS: Record<LegalDocId, LegalDoc> = {
  terms: {
    id: "terms",
    title: "服务条款",
    updated: "2026-09-04",
    paragraphs: [
      TARKOV_PUBLIC_DISCLAIMER,
      "战鸽数据提供账号、圈子功能，以及逃离塔科夫图鉴与联机房间等第三方工具。使用即表示你同意本条款。",
      "联机房间供队友协作勾选任务、标点与声明钥匙，不提供透视、雷达或任何修改游戏的能力。截图同步只解析你本机游戏截图文件名中的坐标，并仅广播给同一房间的队友。",
      RAID_ROOM_TITLE_POLICY +
        "运营者可删除违规房间或限制账号。禁止利用本站从事违法活动或干扰他人游戏。",
      "图鉴数据来自 tarkov.dev 等社区来源，可能滞后或不准确。游戏本身及其商标归 Battlestate Games 所有。",
      "服务按现状提供。公开引流时容量为单机部署，高峰可能降级或暂停联机房间。我们可随时调整功能或下线模块。",
      `请同时遵守《逃离塔科夫》用户协议、B 站等平台规范，以及你所在地的法律。本站已办理 ICP 备案（${ICP_BEIAN_NO}）。`,
    ],
  },
  privacy: {
    id: "privacy",
    title: "隐私说明",
    updated: "2026-09-04",
    paragraphs: [
      "我们收集账号注册所用的邮箱或 QQ 互联标识、显示名，以及你主动填写的资料。JWT 登录态存在浏览器本地。",
      "联机房间会保存房间标题、地图、成员显示名、任务认领、钥匙声明、地图记号与简要在线状态。公开大厅可看到公开房的名称、地图、人数和在座昵称。私密房需密码才能入座；未入座者看不到棋盘、钥匙与人员名单。",
      "战局日志在你的浏览器本机解析。服务器只保存地图、战局编号、时间等摘要，不保存游戏日志原文，也不保存截图文件。",
      "若你绑定森空岛等平台签到，相关凭证加密存库，仅用于你发起的签到或盒子查询。宣传塔科夫功能时，不要求绑定这些平台。",
      "日志与访问记录用于排障和防滥用。我们不会把个人数据出售给广告商。",
      "可通过个人中心改资料、解绑 QQ。删除账号请联系运营者。继续使用即视为了解本说明。",
    ],
  },
};

export function legalDoc(id: LegalDocId): LegalDoc {
  return LEGAL_DOCS[id];
}
