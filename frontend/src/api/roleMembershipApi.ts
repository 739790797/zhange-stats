/** 四平台角色「加入本站」探测 / 批量写入。 */

import { client } from "./http";
import type { RoleMembershipTree } from "@/components/RoleMembershipTreeModal";

export type CheckinPlatformKey = "skland" | "taygedo" | "exilium" | "kujiequ";

export type RoleMembershipReplaceBody = {
  roles: Array<{
    game_code: string;
    role_uid: string;
    included: boolean;
  }>;
};

const STATUS_PATH: Record<CheckinPlatformKey, string> = {
  skland: "/skland",
  taygedo: "/taygedo",
  exilium: "/exilium",
  kujiequ: "/kujiequ",
};

type RoleMembershipTreeOut = {
  platform: string;
  roles?: Array<{
    game_code: string;
    game_name: string;
    role_uid: string;
    role_name: string;
    channel_name?: string | null;
    included?: boolean;
  }>;
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
