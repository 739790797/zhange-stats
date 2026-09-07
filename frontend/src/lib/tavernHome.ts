import type { ArticleListItem } from "@/api/articlesApi";
import { TAVERN_WELCOME_SLUG } from "@/lib/tavernNav";

/** 侧栏「重点关注」：欢迎文置顶，其余按最新补齐。 */
export function pickTavernHighlights(
  latest: ArticleListItem[],
  welcome?: ArticleListItem | null,
  limit = 5,
): ArticleListItem[] {
  const out: ArticleListItem[] = [];
  const seen = new Set<number>();
  const pin =
    welcome && welcome.slug === TAVERN_WELCOME_SLUG ? welcome : undefined;
  if (pin) {
    out.push(pin);
    seen.add(pin.id);
  }
  for (const item of latest) {
    if (out.length >= limit) break;
    if (seen.has(item.id)) continue;
    out.push(item);
    seen.add(item.id);
  }
  return out;
}
