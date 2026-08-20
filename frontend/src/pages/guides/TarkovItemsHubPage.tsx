import { Link, Navigate, useSearchParams } from "react-router-dom";
import { TarkovItemsPageShell } from "@/components/guides/tarkov/TarkovItemsPageShell";
import {
  TARKOV_HANDBOOK_ROOTS,
  handbookHref,
  itemTypeHref,
  resolveItemTypeKey,
} from "@/lib/tarkovItemTypes";
import styles from "@/components/guides/tarkov/TarkovItemsPageShell.module.css";

/** 手册一级总览；旧 ?tab= 深链转到对应分类。 */
export default function TarkovItemsHubPage() {
  const [params] = useSearchParams();
  const typeKey = resolveItemTypeKey(params.get("tab"));
  if (typeKey) {
    const next = new URLSearchParams(params);
    next.delete("tab");
    const qs = next.toString();
    return (
      <Navigate to={`${itemTypeHref(typeKey)}${qs ? `?${qs}` : ""}`} replace />
    );
  }
  return (
    <TarkovItemsPageShell
      title="物品"
      crumbs={[]}
      sectionLabel="物品"
      subtitle="按游戏手册一级分类浏览"
    >
      <div className={styles.hubGrid}>
        {TARKOV_HANDBOOK_ROOTS.map((root) => (
          <Link key={root.slug} className={styles.hubCard} to={handbookHref(root)}>
            <span className={styles.hubLabel}>{root.label}</span>
            {root.children.length ? (
              <span className={styles.hubMeta}>{root.children.length} 个子类</span>
            ) : null}
          </Link>
        ))}
      </div>
    </TarkovItemsPageShell>
  );
}
