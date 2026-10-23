import type { components } from "@/shared/api/generated/schema";
import type { CheckinResponse } from "@/features/platforms/shared/api/types";

export type MihoyoStatus = components["schemas"]["MihoyoStatusOut"];

export type MihoyoBindSmsSendResponse =
  components["schemas"]["MihoyoBindSmsSendResponse"];

export type MihoyoBindPasswordResponse =
  components["schemas"]["MihoyoBindPasswordResponse"];

export type MihoyoQrStart = components["schemas"]["MihoyoQrStartResponse"];

export type MihoyoQrPoll = components["schemas"]["MihoyoQrPollResponse"];

export type MihoyoCheckinResponse = CheckinResponse;

export type MihoyoExchangeItem =
  components["schemas"]["MihoyoExchangeItemOut"];

export type MihoyoExchangeShop =
  components["schemas"]["MihoyoExchangeShopOut"];

export type MihoyoExchangeResult =
  components["schemas"]["MihoyoExchangeResultOut"];

export type MihoyoExchangeRole =
  components["schemas"]["MihoyoExchangeRoleOut"];

export type MihoyoAttendanceCalendar =
  components["schemas"]["MihoyoAttendanceCalendarOut"];
