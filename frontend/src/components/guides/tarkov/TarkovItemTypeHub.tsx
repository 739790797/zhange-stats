import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { LockOutlined, SearchOutlined } from "@ant-design/icons";
import {
  TARKOV_HANDBOOK_ROOTS,
  handbookHref,
  type TarkovHandbookRoot,
} from "@/lib/tarkovItemTypes";
import styles from "./TarkovItemTypeHub.module.css";

const VISIBLE_TAGS = 3;

function matchesQuery(root: TarkovHandbookRoot, q: string): boolean {
  if (!q) return true;
  const hay = [root.label, ...root.children.map((c) => c.label)]
    .join(" ")
    .toLowerCase();
  return hay.includes(q);
}

function CategoryCard({ root }: { root: TarkovHandbookRoot }) {
  const ready = root.status === "ready";
  const href = handbookHref(root);
  const tags = root.children.slice(0, VISIBLE_TAGS);
  const more = Math.max(0, root.children.length - VISIBLE_TAGS);

  return (
    <Link
      to={href}
      className={`${styles.card} ${ready ? styles.cardReady : styles.cardSoon}`}
    >
      <span className={`${styles.corner} ${styles.tl}`} aria-hidden />
      <span className={`${styles.corner} ${styles.tr}`} aria-hidden />
      <span className={`${styles.corner} ${styles.bl}`} aria-hidden />
      <span className={`${styles.corner} ${styles.br}`} aria-hidden />

      <div className={styles.iconStage}>
        {ready ? (
          <span className={styles.iconBox} aria-hidden />
        ) : (
          <LockOutlined className={styles.lockIcon} />
        )}
      </div>

      <div className={styles.cardBody}>
        <div className={styles.titleRow}>
          <span className={styles.cardTitle}>{root.label}</span>
          {ready ? <span className={styles.badgeOpen}>已开放</span> : null}
        </div>
        <div className={styles.subMeta}>
          SUBCLASSES: {root.children.length}
        </div>
        {root.children.length ? (
          <div className={styles.tagRow}>
            {tags.map((child) => (
              <span key={child.id} className={styles.tag}>
                {child.label}
              </span>
            ))}
            {more > 0 ? (
              <span className={`${styles.tag} ${styles.tagMore}`}>
                +{more} More
              </span>
            ) : null}
          </div>
        ) : (
          <div className={styles.tagRowEmpty}>—</div>
        )}
      </div>
    </Link>
  );
}

/** 物品分类检索：贴近 Figma 战术暗色目录 */
export function TarkovItemTypeHub() {
  const [query, setQuery] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const normalized = query.trim().toLowerCase();

  const roots = useMemo(
    () =>
      TARKOV_HANDBOOK_ROOTS.filter((root) => matchesQuery(root, normalized)),
    [normalized],
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        inputRef.current?.focus();
        inputRef.current?.select();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className={styles.shell}>
      <div className={styles.top}>
        <div className={styles.headerRow}>
          <h1 className={styles.title}>物品分类检索</h1>
          <label className={styles.search}>
            <SearchOutlined className={styles.searchIcon} />
            <input
              ref={inputRef}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="输入关键字过滤分类…"
              aria-label="过滤分类"
            />
            <kbd className={styles.kbd}>CTRL+K</kbd>
          </label>
        </div>

        <div className={styles.rule}>
          <span className={styles.ruleAccent} />
          <span className={styles.ruleLine} />
          <span className={styles.ruleCode}>DATABASE_SEC_ITEMS</span>
        </div>
      </div>

      <div className={styles.grid}>
        {roots.map((root) => (
          <CategoryCard key={root.id} root={root} />
        ))}
      </div>

      {!roots.length ? (
        <div className={styles.empty}>无匹配分类</div>
      ) : null}

      <div className={styles.infoBar}>
        <div className={styles.infoText}>
          <span className={styles.infoMark}>i</span>
          点击卡片可深入检索对应子类别的物品详细参数、弹道伤害、藏身处用途及跳蚤市场实时参考价格。
        </div>
        <div className={styles.infoMeta}>
          [ CURRENT SPRINT TARGET: TERMINAL_B ]
        </div>
      </div>
    </div>
  );
}
