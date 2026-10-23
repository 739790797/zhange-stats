import type { ReactNode } from "react";
import { Link, Navigate, useLocation, useParams } from "react-router-dom";
import { apiError } from "@/shared/api/apiError";
import { useRor2Catalog } from "@/features/guides/ror2/hooks/useRor2Catalog";
import { ROR2_ITEMS_PATH, ror2DlcMark, ror2ItemCooldownText } from "@/features/guides/ror2/model/ror2Home";
import { ror2ItemExpansionZh } from "@/features/guides/ror2/model/ror2ItemZh";
import { ror2ItemRouteId } from "@/features/guides/ror2/model/ror2ItemDetail";
import { ror2ItemTableStackTexts, ror2RarityAccent } from "@/features/guides/ror2/model/ror2Catalog";
import { Ror2ExpansionIcon } from "./Ror2ExpansionIcon";
import { Ror2ExpansionName } from "./Ror2ExpansionName";
import { Ror2ItemIcon } from "./Ror2ItemIcon";
import { Ror2RichText } from "./Ror2RichText";
import { Ror2TokenText } from "./Ror2TokenText";
import styles from "./Ror2ItemDetailView.module.css";
import theme from "./ror2Theme.module.css";

export function Ror2ItemDetailView() {
  const { itemKind = "", itemId = "" } = useParams<{ itemKind: string; itemId: string }>();
  const location = useLocation();
  const catalog = useRor2Catalog();
  const rows = itemKind === "equipment"
    ? catalog.data?.equipment
    : itemKind === "item"
      ? catalog.data?.items
      : undefined;
  const item = rows?.find((row) => ror2ItemRouteId(row) === itemId);
  const backTo = `${ROR2_ITEMS_PATH}${location.search}`;

  if (catalog.isPending) return <p className={styles.status}>正在读取图鉴</p>;
  if (catalog.isError) {
    return (
      <div className={styles.status}>
        <p>{apiError(catalog.error, "图鉴暂时拉不下来，请稍后再试")}</p>
        <button type="button" className={theme.wikiBtn} onClick={() => void catalog.refetch()}>
          重试
        </button>
      </div>
    );
  }
  if (catalog.data && !item) return <Navigate to={backTo} replace />;
  if (!item) return null;

  const name = item.localizedText.name;
  const quote = item.localizedText.quote;
  const description = item.localizedText.description;
  const lore = item.localizedText.lore;
  const unlock = item.localizedText.unlock;
  const dlc = ror2DlcMark(item.expansion);
  const rarity = item.localizedText.rarity;
  const stack = ror2ItemTableStackTexts(item.stats);
  const cooldown = ror2ItemCooldownText(item.cooldown);

  return (
    <article className={styles.page}>
      <Link className={theme.wikiBtn} to={backTo}>← 返回物品列表</Link>
      <header className={styles.hero}>
        <Ror2ItemIcon src={item.image_url} accent={ror2RarityAccent(item.rarity)} />
        <div className={styles.identity}>
          <div className={styles.titleRow}>
            <h1 className={styles.title}>
              {dlc ? <Ror2ExpansionIcon src={dlc.iconUrl} label={ror2ItemExpansionZh(dlc.id, dlc.label)} /> : null}
              <Ror2TokenText value={name} />
            </h1>
            <dl className={styles.highlights}>
              <div className={`${styles.highlight} ${styles.quality}`}>
                <dt>品质：</dt>
                <dd>{rarity.text ? <Ror2TokenText value={rarity} /> : "—"}</dd>
              </div>
              <div className={styles.highlight}>
                <dt>堆叠：</dt>
                <dd>
                  {stack.length
                    ? stack.map((value, index) => (
                        <span key={`${value.original}-${index}`}>
                          {index ? " / " : ""}
                          <Ror2TokenText value={value} />
                        </span>
                      ))
                    : "—"}
                </dd>
              </div>
            </dl>
          </div>
          {cooldown || item.expansion ? (
            <dl className={styles.attributes}>
              {cooldown ? (
                <div>
                  <dt>冷却时间</dt>
                  <dd>{cooldown}</dd>
                </div>
              ) : null}
              {item.expansion ? (
                <div>
                  <dt>来源</dt>
                  <dd><Ror2ExpansionName id={item.expansion} fallback={item.expansion} wikiArticles={catalog.data?.wiki_articles} /></dd>
                </div>
              ) : null}
            </dl>
          ) : null}
        </div>
      </header>

      {quote.text.trim() ? <DetailSection title="简单描述"><Ror2RichText text={quote} /></DetailSection> : null}
      {description.text.trim() ? <DetailSection title="详细描述"><Ror2RichText text={description} /></DetailSection> : null}
      {unlock.text.trim() ? <DetailSection title="解锁方式"><Ror2RichText text={unlock} /></DetailSection> : null}
      {lore.text.trim() ? <DetailSection title="日志"><Ror2RichText text={lore} /></DetailSection> : null}
      {item.wiki_url ? (
        <p className={styles.wikiLink}>
          <a href={item.wiki_url} target="_blank" rel="noreferrer">查看 Wiki 原页面</a>
        </p>
      ) : null}
    </article>
  );
}

function DetailSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className={styles.section}>
      <h2>{title}</h2>
      <div className={styles.sectionText}>{children}</div>
    </section>
  );
}
