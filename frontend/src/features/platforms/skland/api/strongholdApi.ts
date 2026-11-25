import { client } from "@/shared/api/http";
import type { components } from "@/shared/api/generated/schema";

export const strongholdQueryKey = ["arknights-stronghold"] as const;

const path = "/skland/arknights/stronghold";

type Schema = components["schemas"];
export type StrongholdVersion = Schema["StrongholdVersionOut"];
export type StrongholdBond = Schema["StrongholdBondOut"];
export type StrongholdSyncStatus = Schema["StrongholdSyncStatus"];
export type StrongholdMatch = Schema["StrongholdMatchOut"];
export type StrongholdMember = Schema["StrongholdMemberOut"];
export type StrongholdScope = Schema["StrongholdScopeOut"];
export type StrongholdRecord = Schema["StrongholdRecordOut"];
export type StrongholdRecordDetail = Schema["StrongholdRecordDetailOut"];
export type StrongholdMode = NonNullable<StrongholdScope["mode_type"]>;
export type StrongholdOwn = Schema["StrongholdOwnOut"];
export type StrongholdCommunity = Schema["StrongholdCommunityOut"];
export type StrongholdRoleSelection = Schema["StrongholdSyncIn"];
export type StrongholdFilters = {
  season?: string;
  version?: string;
  difficulty?: string;
  mode?: StrongholdMode;
  offset: number;
  limit: number;
};

export async function fetchStrongholdCommunity(
  params: StrongholdFilters & { member?: number; date?: string },
) {
  return (await client.get<StrongholdCommunity>(`${path}/community`, { params })).data;
}

export async function fetchStrongholdOwn(
  params: StrongholdFilters & { role_id?: number; result?: "complete" | "interrupted" | "unknown" },
) {
  return (await client.get<StrongholdOwn>(`${path}/me`, { params })).data;
}

export async function fetchStrongholdReport(id: string) {
  return (await client.get<StrongholdMatch>(`${path}/reports/${id}`)).data;
}

export async function fetchStrongholdRecord(id: string) {
  return (await client.get<StrongholdRecordDetail>(`${path}/views/${id}`)).data;
}

export async function syncStrongholdRole(body: StrongholdRoleSelection) {
  return (await client.post<StrongholdSyncStatus>(`${path}/sync`, body)).data;
}
