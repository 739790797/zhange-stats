import type { Ror2WikiArticle } from "@/features/guides/ror2/api/ror2Api";
import { ror2ExpansionName, ror2ExpansionWikiTitle } from "@/features/guides/ror2/model/ror2Expansion";
import { Ror2TokenText } from "./Ror2TokenText";

type Props = {
  id: string;
  fallback?: string;
  wikiArticles?: readonly Ror2WikiArticle[];
  showInfo?: boolean;
};

/**
 * 资料片名仍以 Wiki 标题作为令牌原文；无匹配源单元时使用玩家提供的官方简中名，且不伪造令牌。
 */
export function Ror2ExpansionName({ id, fallback, wikiArticles, showInfo = true }: Props) {
  const sourceTitle = ror2ExpansionWikiTitle(wikiArticles, id);
  if (sourceTitle?.token) {
    return <Ror2TokenText value={sourceTitle} showInfo={showInfo} />;
  }

  return <>{ror2ExpansionName(id, fallback) || fallback || id}</>;
}
