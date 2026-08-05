import { client } from "./http";
import type {
  MemberPlayStats,
  SteamDayData,
  SteamNowItem,
  SteamPollResult,
  SteamAppStoreCard,
} from "./types";

export async function fetchMemberPlayStats(memberId: number) {
  const { data } = await client.get<MemberPlayStats>(
    `/steam/members/${memberId}`,
  );
  return data;
}

export async function fetchSteamDay(date: string, end?: string) {
  const { data } = await client.get<SteamDayData>("/steam/day", {
    params: {
      date,
      ...(end ? { end } : {}),
    },
  });
  return data;
}

export async function fetchSteamNow() {
  const { data } = await client.get<SteamNowItem[]>("/steam/now");
  return data;
}

export async function fetchSteamAppStore(appId: string) {
  const { data } = await client.get<SteamAppStoreCard>(`/steam/apps/${appId}`);
  return data;
}

export async function fetchSteamAppIcon(appId: string) {
  const { data } = await client.get<{ steam_app_id: string; icon_url: string | null }>(
    `/steam/apps/${encodeURIComponent(appId)}/icon`,
  );
  return data;
}

export async function triggerSteamPoll() {
  const { data } = await client.post<SteamPollResult>("/steam/poll");
  return data;
}
