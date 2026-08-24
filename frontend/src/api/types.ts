import type { components } from "./generated/schema";

/** 与后端 OpenAPI `UserOut` 对齐（单一契约源）。 */
export type User = components["schemas"]["UserOut"];

/** 与后端 OpenAPI `TokenResponse` 对齐。 */
export type TokenResponse = components["schemas"]["TokenResponse"];

/** 与后端 OpenAPI `UserBrief` 对齐。 */
export type UserBrief = components["schemas"]["UserBrief"];

/** 与后端 OpenAPI `MemberProfileOut` 对齐。 */
export type MemberProfile = components["schemas"]["MemberProfileOut"];

/** 与后端 OpenAPI 平台状态 / 签到响应对齐。 */
export type SklandStatus = components["schemas"]["SklandStatusOut"];
export type TaygedoStatus = components["schemas"]["TaygedoStatusOut"];
export type TaygedoAttendanceCalendar =
  components["schemas"]["TaygedoAttendanceCalendarOut"];
export type ExiliumStatus = components["schemas"]["ExiliumStatusOut"];
export type KujiequStatus = components["schemas"]["KujiequStatusOut"];
export type MihoyoStatus = components["schemas"]["MihoyoStatusOut"];
export type MihoyoBindSmsSendResponse =
  components["schemas"]["MihoyoBindSmsSendResponse"];
export type MihoyoBindPasswordResponse =
  components["schemas"]["MihoyoBindPasswordResponse"];
export type MihoyoQrStart = components["schemas"]["MihoyoQrStartResponse"];
export type MihoyoQrPoll = components["schemas"]["MihoyoQrPollResponse"];

export type CheckinResponse = components["schemas"]["CheckinResponse"];
export type SklandCheckinResponse = CheckinResponse;
export type TaygedoCheckinResponse = CheckinResponse;
export type ExiliumCheckinResponse = CheckinResponse;
export type KujiequCheckinResponse = CheckinResponse;
export type MihoyoCheckinResponse = CheckinResponse;

/** Steam / 盒子对比等与 OpenAPI 对齐。 */
export type SteamNowItem = components["schemas"]["SteamNowItem"];
export type SteamPollResult = components["schemas"]["SteamPollResult"];
export type EndfieldBox = components["schemas"]["EndfieldBoxOut"];
export type ExastrisBox = components["schemas"]["ExastrisBoxOut"];
export type ExastrisChar = components["schemas"]["ExastrisCharOut"];
export type ArknightsRogue = components["schemas"]["ArknightsRogueOut"];
export type ArknightsRogueRecord =
  components["schemas"]["ArknightsRogueRecordOut"];
export type ArknightsBoxCompare = components["schemas"]["ArknightsBoxCompareOut"];
export type ArknightsAttendanceCalendar =
  components["schemas"]["ArknightsAttendanceCalendarOut"];
export type EndfieldAttendanceCalendar =
  components["schemas"]["EndfieldAttendanceCalendarOut"];
export type GameScheduleEvent =
  components["schemas"]["GameScheduleEventOut"];
export type GameScheduleCalendar =
  components["schemas"]["GameScheduleCalendarOut"];

export type ArknightsOperator = components["schemas"]["ArknightsOperatorOut"];
export type ArknightsOwnedChar = components["schemas"]["ArknightsOwnedCharOut"];
export type ArknightsCompareCandidate =
  components["schemas"]["ArknightsCompareCandidateOut"];
export type ArknightsCompareRow = components["schemas"]["ArknightsCompareRowOut"];

export type EndfieldEquip = components["schemas"]["EndfieldEquipOut"];
export type EndfieldSkill = components["schemas"]["EndfieldSkillOut"];
export type EndfieldChar = components["schemas"]["EndfieldCharOut"];

export type SteamDayData = components["schemas"]["SteamDayResponse"];
export type SteamTimelineRow = components["schemas"]["SteamTimelineRow"];
export type SteamAppStoreCard = components["schemas"]["SteamAppStoreCard"];

export type SklandQrStart = components["schemas"]["SklandQrStartResponse"];
export type SklandQrPoll = components["schemas"]["SklandQrPollResponse"];
export type KujiequSmsSendResponse =
  components["schemas"]["KujiequBindSmsSendResponse"];
export type ExiliumSmsSendResponse =
  components["schemas"]["ExiliumBindSmsSendResponse"];
export type ExiliumExchangeItem =
  components["schemas"]["ExiliumExchangeItemOut"];
export type ExiliumExchangeShop =
  components["schemas"]["ExiliumExchangeShopOut"];
export type ExiliumExchangeResult =
  components["schemas"]["ExiliumExchangeResultOut"];

export type KujiequExchangeItem =
  components["schemas"]["KujiequExchangeItemOut"];
export type KujiequExchangeShop =
  components["schemas"]["KujiequExchangeShopOut"];
export type KujiequExchangeResult =
  components["schemas"]["KujiequExchangeResultOut"];
export type MihoyoExchangeItem =
  components["schemas"]["MihoyoExchangeItemOut"];
export type MihoyoExchangeShop =
  components["schemas"]["MihoyoExchangeShopOut"];
export type MihoyoExchangeResult =
  components["schemas"]["MihoyoExchangeResultOut"];
export type KujiequExchangeRole =
  components["schemas"]["KujiequExchangeRoleOut"];

export type TaygedoExchangeItem =
  components["schemas"]["TaygedoExchangeItemOut"];
export type TaygedoExchangeShop =
  components["schemas"]["TaygedoExchangeShopOut"];
export type TaygedoExchangeResult =
  components["schemas"]["TaygedoExchangeResultOut"];
export type TaygedoExchangeRole =
  components["schemas"]["TaygedoExchangeRoleOut"];

export type KujiequAttendanceCalendar =
  components["schemas"]["KujiequAttendanceCalendarOut"];
export type WwBox = components["schemas"]["WwBoxOut"];
export type WwBoxItem = components["schemas"]["WwBoxItemOut"];

/** 与后端 OpenAPI `MemberPlayStatsResponse` 对齐。 */
export type MemberPlayStats = components["schemas"]["MemberPlayStatsResponse"];

export function formatDuration(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (h > 0) return `${h} 小时 ${m} 分`;
  if (m > 0) return `${m} 分钟`;
  return `${s} 秒`;
}
