import type { components } from "@/shared/api/generated/schema";
import type { CheckinResponse } from "@/features/platforms/shared/api/types";

export type SklandStatus = components["schemas"]["SklandStatusOut"];

export type SklandCheckinResponse = CheckinResponse;

export type EndfieldBox = components["schemas"]["EndfieldBoxOut"];

export type EndfieldBoxCompare = components["schemas"]["EndfieldBoxCompareOut"];

export type EndfieldCompareCandidate =
  components["schemas"]["EndfieldCompareCandidateOut"];

export type EndfieldCompareRow =
  components["schemas"]["EndfieldCompareRowOut"];

export type EndfieldOperator = components["schemas"]["EndfieldOperatorOut"];

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

export type SklandQrStart = components["schemas"]["SklandQrStartResponse"];

export type SklandQrPoll = components["schemas"]["SklandQrPollResponse"];
