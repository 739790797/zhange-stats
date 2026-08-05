import { client } from "./http";

export interface NapCatGroup {
  group_id: string;
  group_name: string;
  member_count?: number | null;
  max_member_count?: number | null;
}

export interface NapCatSiteMember {
  id: number;
  nickname: string;
  user_id?: number | null;
  qq_number?: string | null;
}

export interface NapCatGroupMember {
  user_id: string;
  nickname: string;
  card: string;
  role: string;
  title: string;
  site_member: NapCatSiteMember | null;
}

export interface NapCatGroupsResponse {
  configured: boolean;
  groups: NapCatGroup[];
}

export interface NapCatGroupMembersResponse {
  group_id: string;
  members: NapCatGroupMember[];
  site_bound_count: number;
}

export async function testNapCatConnection(payload: {
  base_url?: string;
  token?: string | null;
}) {
  const { data } = await client.post<{
    ok: boolean;
    message: string;
    user_id?: string | null;
    nickname?: string | null;
  }>("/napcat/test", payload, { timeout: 15000 });
  return data;
}

export async function fetchNapCatGroups(force = false) {
  const { data } = await client.get<NapCatGroupsResponse>("/napcat/groups", {
    params: force ? { force: true } : undefined,
    timeout: 60000,
  });
  return data;
}

export async function fetchNapCatGroupMembers(groupId: string, force = false) {
  const { data } = await client.get<NapCatGroupMembersResponse>(
    `/napcat/groups/${encodeURIComponent(groupId)}/members`,
    {
      params: force ? { force: true } : undefined,
      timeout: 60000,
    },
  );
  return data;
}
