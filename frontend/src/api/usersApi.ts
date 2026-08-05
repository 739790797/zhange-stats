import { client } from "./http";
import type { MemberProfile, UserBrief } from "./types";

export async function fetchUsers() {
  const { data } = await client.get<UserBrief[]>("/users");
  return data;
}

export async function createUser(payload: {
  email: string;
  display_name: string;
  password: string;
  steam_id?: string | null;
}) {
  const { data } = await client.post<UserBrief>("/users", payload);
  return data;
}

export async function updateUser(
  userId: number,
  payload: {
    email?: string;
    display_name?: string;
    password?: string;
    steam_id?: string | null;
    role?: "admin" | "user";
    is_admin?: boolean;
  },
) {
  const { data } = await client.patch<UserBrief>(`/users/${userId}`, payload);
  return data;
}

export async function deleteUser(userId: number) {
  await client.delete(`/users/${userId}`);
}

export async function fetchMyProfile() {
  const { data } = await client.get<MemberProfile>("/profile/me");
  return data;
}

export async function startSteamOpenIdBind(memberId?: number) {
  const { data } = await client.get<{ url: string }>("/profile/steam/openid/start", {
    params: memberId != null ? { member_id: memberId } : undefined,
  });
  return data;
}

export async function startQqOAuthBind(memberId?: number) {
  const { data } = await client.get<{ url: string }>("/profile/qq/oauth/start", {
    params: memberId != null ? { member_id: memberId } : undefined,
  });
  return data;
}

export async function unbindQq(memberId?: number) {
  const { data } = await client.delete<MemberProfile>("/profile/qq", {
    params: memberId != null ? { member_id: memberId } : undefined,
  });
  return data;
}

export async function updateMyProfile(payload: {
  display_name?: string;
  steam_id?: string | null;
  qq_number?: string | null;
}) {
  const { data } = await client.patch<MemberProfile>("/profile/me", payload);
  return data;
}

export async function uploadMyAvatar(file: File) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await client.post<MemberProfile>("/profile/me/avatar", form, {
    timeout: 30000,
  });
  return data;
}

export async function uploadMemberAvatar(memberId: number, file: File) {
  const form = new FormData();
  form.append("file", file);
  const { data } = await client.post<MemberProfile>(
    `/members/${memberId}/avatar`,
    form,
    { timeout: 30000 },
  );
  return data;
}

export async function fetchMemberProfile(memberId: number) {
  const { data } = await client.get<MemberProfile>(
    `/members/${memberId}/profile`,
  );
  return data;
}

export async function updateMemberProfile(
  memberId: number,
  payload: {
    display_name?: string;
    steam_id?: string | null;
    qq_number?: string | null;
  },
) {
  const { data } = await client.patch<MemberProfile>(
    `/members/${memberId}/profile`,
    payload,
  );
  return data;
}
