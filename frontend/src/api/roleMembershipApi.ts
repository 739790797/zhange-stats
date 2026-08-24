/** 四平台角色「加入本站」探测 / 批量写入。 */

import { client } from "./http";
import type { components } from "@/api/generated/schema";

export type CheckinPlatformKey = "skland" | "taygedo" | "exilium" | "kujiequ" | "mihoyo";

export type RoleMembershipReplaceBody =
  components["schemas"]["RoleMembershipReplaceBody"];
export type RoleMembershipTreeOut =
  components["schemas"]["RoleMembershipTreeOut"];
export type RoleMembershipNode =
  components["schemas"]["RoleMembershipNodeOut"];

/** 前端树组件用：channel_name 非空、included 布尔化 */
export type RoleMembershipTree = {
  platform: string;
  roles: Array<
    RoleMembershipNode & { channel_name: string; included: boolean }
  >;
};

const STATUS_PATH: Record<CheckinPlatformKey, string> = {
  skland: "/skland",
  taygedo: "/taygedo",
  exilium: "/exilium",
  kujiequ: "/kujiequ",
  mihoyo: "/mihoyo",
};

export async function fetchRoleMembershipTree(
  platform: CheckinPlatformKey,
): Promise<RoleMembershipTree> {
  const { data } = await client.get<RoleMembershipTreeOut>(
    `${STATUS_PATH[platform]}/role-tree`,
  );
  return {
    platform: data.platform,
    roles: (data.roles || []).map((r) => ({
      game_code: r.game_code,
      game_name: r.game_name,
      role_uid: r.role_uid,
      role_name: r.role_name,
      channel_name: r.channel_name || "",
      included: Boolean(r.included),
    })),
  };
}

export async function replaceRoleMemberships(
  platform: CheckinPlatformKey,
  roles: RoleMembershipReplaceBody["roles"],
) {
  const { data } = await client.put(
    `${STATUS_PATH[platform]}/role-memberships`,
    { roles } satisfies RoleMembershipReplaceBody,
  );
  return data;
}
