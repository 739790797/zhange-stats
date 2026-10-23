/**
 * 塔科夫本机个人进度（任务账、钥匙、3×4 收集、阵营、备战步骤）跟着账号走。
 * 换人或登出时先处理本机这份，免得上一位的进度被并进下一位的账号。
 */

export const TARKOV_PROGRESS_OWNER_KEY = "zhange.guides.tarkov.progressOwner.v1";
export const TARKOV_GUEST_PROGRESS_KEY = "zhange.guides.tarkov.guestProgress.v1";
export const TARKOV_GUEST_OWNER = "guest";

/** 与各模块的存储键一致（单测对照）；写字面量是为了不让入口包把塔科夫模块带进来。 */
export const TARKOV_PERSONAL_STORAGE_KEYS = [
  "zhange.guides.tarkov.taskDones.v1",
  "zhange.guides.tarkov.keyPacks.v1",
  "zhange.guides.tarkov.collectionOwns.v1",
  "zhange.guides.tarkov.collectionLayout.v2",
  "zhange.guides.tarkov.collectionLayout.v3",
  "zhange.guides.tarkov.pmcFaction.v1",
  "zhange.tarkov.raidPrep.objDone.v1",
] as const;

export type TarkovProgressOwnerAction = "keep" | "adopt" | "clear" | "stash";

export type TarkovGuestProgress = Partial<Record<string, string>>;

type ProgressStorage = Pick<Storage, "getItem" | "setItem" | "removeItem">;

export function browserLocalStorage(): Storage | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage;
  } catch {
    return null;
  }
}

export function tarkovProgressOwnerOf(userId: number | null | undefined): string {
  return userId ? `user:${userId}` : TARKOV_GUEST_OWNER;
}

/**
 * stored：本机进度记在谁名下；next：现在是谁；leaving：本标签页刚离开的身份（别的标签页可能已改过 stored）。
 * - 没有标记（升级前的旧数据）：认当前身份，原样保留；
 * - 离开某个账号（登出 / 换号）：清掉，下一位以自己的账号进度为准；
 * - 访客 → 账号：先收进访客暂存，等用户确认要不要并进账号。
 */
export function planTarkovProgressOwner(input: {
  stored: string | null | undefined;
  next: string;
  leaving?: string | null;
}): TarkovProgressOwnerAction {
  const { stored, next, leaving } = input;
  if (leaving && leaving !== TARKOV_GUEST_OWNER && leaving !== next) return "clear";
  if (stored === next) return "keep";
  if (!stored) return "adopt";
  if (stored === TARKOV_GUEST_OWNER) return "stash";
  return "clear";
}

function parseGuestProgress(raw: string | null): TarkovGuestProgress {
  if (!raw) return {};
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return {};
    const out: TarkovGuestProgress = {};
    for (const key of TARKOV_PERSONAL_STORAGE_KEYS) {
      const value = (parsed as Record<string, unknown>)[key];
      if (typeof value === "string" && value) out[key] = value;
    }
    return out;
  } catch {
    return {};
  }
}

/** 按当前身份认领本机进度；返回这次做了什么。 */
export function claimTarkovProgressOwner(
  storage: ProgressStorage,
  userId: number | null | undefined,
  previousUserId?: number | null,
): TarkovProgressOwnerAction {
  const next = tarkovProgressOwnerOf(userId);
  try {
    const action = planTarkovProgressOwner({
      stored: storage.getItem(TARKOV_PROGRESS_OWNER_KEY),
      next,
      leaving:
        previousUserId === undefined ? null : tarkovProgressOwnerOf(previousUserId),
    });
    if (action === "keep") return action;
    if (action === "stash") {
      const stash = parseGuestProgress(storage.getItem(TARKOV_GUEST_PROGRESS_KEY));
      let moved = false;
      for (const key of TARKOV_PERSONAL_STORAGE_KEYS) {
        const value = storage.getItem(key);
        if (value == null) continue;
        stash[key] = value;
        moved = true;
      }
      if (moved) {
        try {
          storage.setItem(TARKOV_GUEST_PROGRESS_KEY, JSON.stringify(stash));
        } catch {
          /* 存不下就丢：宁可丢访客进度，也不能不经确认并进账号 */
        }
      }
    }
    if (action === "stash" || action === "clear") {
      for (const key of TARKOV_PERSONAL_STORAGE_KEYS) storage.removeItem(key);
    }
    storage.setItem(TARKOV_PROGRESS_OWNER_KEY, next);
    return action;
  } catch {
    return "keep";
  }
}

/** 登录前在本浏览器记下、还没决定要不要并进账号的进度；没有则 null。 */
export function readTarkovGuestProgress(
  storage: Pick<Storage, "getItem">,
): TarkovGuestProgress | null {
  try {
    const stash = parseGuestProgress(storage.getItem(TARKOV_GUEST_PROGRESS_KEY));
    return Object.keys(stash).length ? stash : null;
  } catch {
    return null;
  }
}

export function discardTarkovGuestProgress(
  storage: Pick<Storage, "removeItem">,
): void {
  try {
    storage.removeItem(TARKOV_GUEST_PROGRESS_KEY);
  } catch {
    /* ignore private mode */
  }
}
