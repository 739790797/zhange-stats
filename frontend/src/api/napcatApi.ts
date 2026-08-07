import { client } from "./http";
import type { components } from "./generated/schema";

export type NapCatGroup = components["schemas"]["NapCatGroupOut"];
export type NapCatSiteMember = components["schemas"]["NapCatSiteMemberOut"];
export type NapCatGroupMember = components["schemas"]["NapCatGroupMemberOut"];
export type NapCatGroupsResponse = components["schemas"]["NapCatGroupsResponse"];
export type NapCatGroupMembersResponse =
  components["schemas"]["NapCatGroupMembersResponse"];
export type NapCatTestRequest = components["schemas"]["NapCatTestRequest"];
export type NapCatTestResponse = components["schemas"]["NapCatTestResponse"];

export async function testNapCatConnection(payload: NapCatTestRequest) {
  const { data } = await client.post<NapCatTestResponse>(
    "/napcat/test",
    payload,
    { timeout: 15000 },
  );
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
