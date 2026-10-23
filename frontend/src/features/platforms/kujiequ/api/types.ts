import type { components } from "@/shared/api/generated/schema";
import type { CheckinResponse } from "@/features/platforms/shared/api/types";

export type KujiequStatus = components["schemas"]["KujiequStatusOut"];

export type KujiequCheckinResponse = CheckinResponse;

export type KujiequSmsSendResponse =
  components["schemas"]["KujiequBindSmsSendResponse"];

export type KujiequExchangeItem =
  components["schemas"]["KujiequExchangeItemOut"];

export type KujiequExchangeShop =
  components["schemas"]["KujiequExchangeShopOut"];

export type KujiequExchangeResult =
  components["schemas"]["KujiequExchangeResultOut"];

export type KujiequExchangeRole =
  components["schemas"]["KujiequExchangeRoleOut"];

export type KujiequAttendanceCalendar =
  components["schemas"]["KujiequAttendanceCalendarOut"];

export type WwBox = components["schemas"]["WwBoxOut"];

export type WwBoxItem = components["schemas"]["WwBoxItemOut"];
