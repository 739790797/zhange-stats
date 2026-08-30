import type { ReactNode } from "react";
import { TarkovTraderThumb } from "@/components/guides/tarkov/TarkovTraderThumb";
import { traderFilterLabel } from "@/lib/tarkovRaidPrep";
import styles from "./TarkovRaidPrepPanel.module.css";

export type RaidPrepTraderChip = {
  id: string;
  slug: string;
  name: string;
};

type Props = {
  keyword: string;
  onKeyword: (value: string) => void;
  traders: RaidPrepTraderChip[];
  trader: string;
  onTrader: (slug: string) => void;
  /** 搜索框上方插槽（如「更换地图」「从任务进度同步」） */
  leading?: ReactNode;
};

export function TarkovRaidPrepFilters({
  keyword,
  onKeyword,
  traders,
  trader,
  onTrader,
  leading,
}: Props) {
  return (
    <>
      {leading}
      <input
        id="raid-prep-search"
        className={styles.dockSearch}
        type="search"
        value={keyword}
        onChange={(event) => onKeyword(event.target.value)}
        placeholder="搜索任务"
        aria-label="搜索任务"
      />
      <div className={styles.moreWrap}>
        <span className={styles.filterLabel}>商人</span>
        <div
          className={styles.traderMiniBar}
          role="radiogroup"
          aria-label="按商人筛选"
        >
          <button
            type="button"
            role="radio"
            aria-checked={!trader}
            className={`${styles.traderMini} ${styles.traderMiniAll} ${
              !trader ? styles.traderMiniOn : ""
            }`}
            onClick={() => onTrader("")}
          >
            全部
          </button>
          {traders.map((item) => {
            const { english, chinese } = traderFilterLabel(
              item.slug,
              item.name,
            );
            const on = trader === item.slug;
            return (
              <button
                key={item.slug || item.id}
                type="button"
                role="radio"
                aria-checked={on}
                aria-label={chinese ? `${english}（${chinese}）` : english}
                title={chinese ? `${english}（${chinese}）` : english}
                className={`${styles.traderMini} ${on ? styles.traderMiniOn : ""}`}
                onClick={() => onTrader(item.slug)}
              >
                <TarkovTraderThumb slug={item.slug} size={32} />
              </button>
            );
          })}
        </div>
      </div>
    </>
  );
}
