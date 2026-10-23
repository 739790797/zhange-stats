import type { components } from "@/shared/api/generated/schema";
import type { CheckinResponse } from "@/features/platforms/shared/api/types";

export type TaygedoStatus = components["schemas"]["TaygedoStatusOut"];

export type TaygedoAttendanceCalendar =
  components["schemas"]["TaygedoAttendanceCalendarOut"];

export type TaygedoCheckinResponse = CheckinResponse;

export type ExastrisBox = components["schemas"]["ExastrisBoxOut"];

export type ExastrisChar = components["schemas"]["ExastrisCharOut"];

export type TaygedoExchangeItem =
  components["schemas"]["TaygedoExchangeItemOut"];

export type TaygedoExchangeShop =
  components["schemas"]["TaygedoExchangeShopOut"];

export type TaygedoExchangeResult =
  components["schemas"]["TaygedoExchangeResultOut"];

export type TaygedoExchangeRole =
  components["schemas"]["TaygedoExchangeRoleOut"];
