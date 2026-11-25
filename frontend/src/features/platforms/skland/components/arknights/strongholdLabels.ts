import type { StrongholdMatch, StrongholdOwn } from "@/features/platforms/skland/api/strongholdApi";
import type { SklandStatus } from "@/features/platforms/skland/api/types";

export const modeLabels = { single: "独立模拟", multi: "联合模拟", local: "教学模拟" };

export const missingRoleName = "角色名未同步";

function knownRoleName(name?: string | null, uid?: string) {
  const value = name?.trim();
  return value && value !== uid && value !== "未知角色" && value !== missingRoleName
    ? value
    : undefined;
}

export function roleLabel(name?: string | null) {
  return knownRoleName(name) ?? missingRoleName;
}

export function roleNamesLabel(names: readonly string[] | undefined, fallback = missingRoleName) {
  return names?.length ? names.join("、") : fallback;
}

export function preferredRoleName(
  current: string | null | undefined,
  cached: string | null | undefined,
  uid: string,
) {
  const name = knownRoleName(current, uid);
  const fallback = knownRoleName(cached, uid);
  return !name || fallback?.match(/^(.+)#[0-9]+$/)?.[1] === name ? fallback : name;
}

export function boundRoleNames(roles: SklandStatus["roles"]) {
  const names = new Map<string, string>();
  for (const role of roles ?? []) {
    const channel = role.channel_master_id;
    const name = knownRoleName(role.role_name, role.uid);
    if (role.game_code === "arknights" && (channel === "1" || channel === "2") && name) {
      const key = `${channel}:${role.uid}`;
      names.set(key, preferredRoleName(name, names.get(key), role.uid) ?? name);
    }
  }
  return names;
}

export function withOwnRoleNames(
  match: StrongholdMatch,
  roles: StrongholdOwn["roles"],
  names: ReadonlyMap<string, string>,
): StrongholdMatch {
  if (!match.views?.length || !roles.length) return match;
  const rolesById = new Map(roles.map((role) => [role.id, role]));
  return {
    ...match,
    views: match.views.map((view) => {
      const role =
        view.is_own && view.own_role_id != null ? rolesById.get(view.own_role_id) : undefined;
      if (!role) return view;
      const { uid, channel_id: channel } = role;
      const cached = preferredRoleName(view.role_name, role.role_name, uid);
      const name = preferredRoleName(names.get(`${channel}:${uid}`), cached, uid);
      return name ? { ...view, role_name: name } : view;
    }),
  };
}
