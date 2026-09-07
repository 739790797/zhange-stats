import { useParams } from "react-router-dom";
import { TarkovGunsPanel } from "@/components/guides/tarkov/TarkovGunsPanel";
import { TarkovItemsPageShell } from "@/components/guides/tarkov/TarkovItemsPageShell";
import { TarkovWorkbenchBuild } from "@/components/guides/tarkov/workbench/TarkovWorkbenchBuild";
import {
  TARKOV_WORKBENCH_PATH,
  tarkovWorkbenchHref,
} from "@/lib/tarkovHomeNav";

export default function TarkovWorkbenchPage() {
  const { gunId } = useParams<{ gunId?: string }>();

  if (gunId) {
    return (
      <TarkovItemsPageShell
        crumbs={[
          { label: "选枪", to: TARKOV_WORKBENCH_PATH },
          { label: "改枪" },
        ]}
        sectionLabel="工作台"
        sectionHref={TARKOV_WORKBENCH_PATH}
        fill
      >
        <TarkovWorkbenchBuild gunId={gunId} />
      </TarkovItemsPageShell>
    );
  }

  return (
    <TarkovItemsPageShell
      title="枪械工作台"
      crumbs={[]}
      sectionLabel="工作台"
      sectionHref={TARKOV_WORKBENCH_PATH}
      subtitle="点枪名或整行进入改枪。图鉴「枪支」表仍打开物品详情。"
    >
      <TarkovGunsPanel
        pickHref={(id) => tarkovWorkbenchHref(id)}
        caliberHref={(caliber) =>
          `${TARKOV_WORKBENCH_PATH}?caliber=${encodeURIComponent(caliber)}`
        }
      />
    </TarkovItemsPageShell>
  );
}
