/** 个人中心资料：白边/蓝边、角色等级、商人好感。 */

import { TARKOV_TRADERS } from "@/lib/tarkovHomeNav";
import {
  TARKOV_STASH_FLOOR_EOD,
  TARKOV_STASH_FLOOR_STANDARD,
} from "@/lib/tarkovHideoutProgress";

export const TARKOV_GAME_EDITIONS = ["standard", "eod"] as const;
export type TarkovGameEdition = (typeof TARKOV_GAME_EDITIONS)[number];

export const TARKOV_PLAYER_LEVEL_MIN = 1;
export const TARKOV_PLAYER_LEVEL_MAX = 79;
export const TARKOV_TRADER_LOYALTY_MIN = 1;
export const TARKOV_TRADER_LOYALTY_MAX = 4;

const SKIP_TRADER_SLUGS = new Set(["btr-driver"]);

export const TARKOV_PROFILE_TRADER_SLUGS = TARKOV_TRADERS.map((row) => row.id).filter(
  (id) => !SKIP_TRADER_SLUGS.has(id),
);

const EDITION_LABEL: Record<TarkovGameEdition, string> = {
  standard: "白边",
  eod: "蓝边",
};

export function parseTarkovGameEdition(raw: unknown): TarkovGameEdition {
  const text = String(raw || "")
    .trim()
    .toLowerCase();
  if (text === "eod" || text === "edge" || text === "blue") return "eod";
  return "standard";
}

export function tarkovGameEditionLabel(edition: TarkovGameEdition): string {
  return EDITION_LABEL[edition];
}

export function tarkovStashFloor(edition: unknown): number {
  return parseTarkovGameEdition(edition) === "eod"
    ? TARKOV_STASH_FLOOR_EOD
    : TARKOV_STASH_FLOOR_STANDARD;
}

export function parseTarkovPlayerLevel(raw: unknown): number {
  const value = Number(raw);
  if (!Number.isFinite(value)) return TARKOV_PLAYER_LEVEL_MIN;
  return Math.min(
    Math.max(Math.trunc(value), TARKOV_PLAYER_LEVEL_MIN),
    TARKOV_PLAYER_LEVEL_MAX,
  );
}

export function parseTarkovTraderLoyalty(raw: unknown): number {
  const value = Number(raw);
  if (!Number.isFinite(value)) return TARKOV_TRADER_LOYALTY_MIN;
  return Math.min(
    Math.max(Math.trunc(value), TARKOV_TRADER_LOYALTY_MIN),
    TARKOV_TRADER_LOYALTY_MAX,
  );
}

export function traderLevelsForHideout(
  stored: Record<string, number> | undefined,
): Record<string, number> | undefined {
  if (!stored) return undefined;
  const keys = Object.keys(stored);
  if (!keys.length) return undefined;
  const out: Record<string, number> = {};
  for (const key of keys) {
    const slug = key.trim().toLowerCase();
    if (!slug) continue;
    out[slug] = parseTarkovTraderLoyalty(stored[key]);
  }
  return Object.keys(out).length ? out : undefined;
}

export type TarkovLoyaltyLevelReq = {
  level?: number;
  required_player_level?: number;
  required_reputation?: number;
};

export type LoyaltyReqPart = {
  key: "level" | "standing";
  text: string;
  met: boolean | null;
};

export function formatTraderStanding(value: number): string {
  if (!Number.isFinite(value) || value === 0) return "0";
  const abs = Math.abs(value);
  const digits = abs >= 1 && Number.isInteger(value) ? 0 : 2;
  return value.toFixed(digits);
}

export function indexTraderLoyaltyBySlug(
  traders:
    | Array<{ slug?: string; levels?: TarkovLoyaltyLevelReq[] }>
    | undefined,
): Map<string, TarkovLoyaltyLevelReq[]> {
  const out = new Map<string, TarkovLoyaltyLevelReq[]>();
  for (const row of traders || []) {
    const slug = (row.slug || "").trim().toLowerCase();
    if (!slug) continue;
    const levels = [...(row.levels || [])].sort(
      (a, b) => Number(a.level || 0) - Number(b.level || 0),
    );
    out.set(slug, levels);
  }
  return out;
}

export function traderLoyaltySpec(
  levels: TarkovLoyaltyLevelReq[] | undefined,
  target: number,
): TarkovLoyaltyLevelReq | undefined {
  return (levels || []).find((row) => Number(row.level || 0) === target);
}

/** 未维护时按 LL1 起算，展示再升一级的门槛。 */
export function remainingTraderLoyaltySpecs(
  levels: TarkovLoyaltyLevelReq[] | undefined,
  current: number,
): TarkovLoyaltyLevelReq[] {
  const now = current > 0 ? current : 1;
  return (levels || []).filter((row) => Number(row.level || 0) > now);
}

export function nextTraderLoyaltySpec(
  levels: TarkovLoyaltyLevelReq[] | undefined,
  current: number,
): TarkovLoyaltyLevelReq | undefined {
  return remainingTraderLoyaltySpecs(levels, current)[0];
}

export function traderLoyaltyReqParts(
  spec: TarkovLoyaltyLevelReq | undefined,
  playerLevel: number,
  opts?: { includeBaseline?: boolean },
): LoyaltyReqPart[] {
  if (!spec) return [];
  const includeBaseline = Boolean(opts?.includeBaseline);
  const parts: LoyaltyReqPart[] = [];
  const needLevel = Number(spec.required_player_level || 0);
  if (includeBaseline || needLevel > 1) {
    const level = needLevel > 0 ? needLevel : TARKOV_PLAYER_LEVEL_MIN;
    parts.push({
      key: "level",
      text: `等级 ${level}`,
      met: playerLevel >= level,
    });
  }
  const standing = Number(spec.required_reputation || 0);
  if (includeBaseline || standing > 0) {
    parts.push({
      key: "standing",
      text: `好感度 ${formatTraderStanding(standing)}`,
      met: null,
    });
  }
  return parts;
}

export function traderLoyaltyReqTitle(
  spec: TarkovLoyaltyLevelReq | undefined,
): string {
  if (!spec) return "";
  const level = Number(spec.level || 0);
  const prefix = level ? `LL${level}` : "";
  const parts = traderLoyaltyReqParts(spec, TARKOV_PLAYER_LEVEL_MAX);
  if (!parts.length) {
    return prefix ? `${prefix}：无额外等级/好感度要求` : "无额外等级/好感度要求";
  }
  const body = parts.map((row) => row.text).join(" · ");
  return prefix ? `${prefix}：${body}` : body;
}
