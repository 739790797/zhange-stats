import { Link } from "react-router-dom";
import { TarkovItemsPageShell } from "@/features/guides/tarkov/components/TarkovItemsPageShell";
import { TARKOV_PROGRESSION } from "@/features/guides/tarkov/model/tarkovHomeNav";
import shell from "@/features/guides/tarkov/components/TarkovItemsPageShell.module.css";
import { TarkovSoonMark } from "@/features/guides/tarkov/components/TarkovGuideShell";

export default function TarkovProgressionPage() {
  return (
    <TarkovItemsPageShell
      title="进度"
      crumbs={[]}
      sectionLabel="进度"
      subtitle="任务图鉴已开放。成就 / 声望仍待上游数据。"
    >
      <div className={shell.hubGrid}>
        {TARKOV_PROGRESSION.map((item) =>
          item.status === "soon" ? (
            <span key={item.id} className={shell.hubCard} aria-disabled="true">
              <span className={shell.hubLabel}>{item.label}</span>
              <span className={shell.hubMeta}>
                <TarkovSoonMark status={item.status} />
              </span>
            </span>
          ) : (
            <Link key={item.id} to={item.href} className={shell.hubCard}>
              <span className={shell.hubLabel}>{item.label}</span>
              <span className={shell.hubMeta}>打开</span>
            </Link>
          ),
        )}
      </div>
    </TarkovItemsPageShell>
  );
}
