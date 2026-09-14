import { useParams } from "react-router-dom";
import { TarkovHideoutPanel } from "@/components/guides/tarkov/TarkovHideoutPanel";
import { TarkovItemsPageShell } from "@/components/guides/tarkov/TarkovItemsPageShell";
import { TARKOV_HIDEOUT_PATH } from "@/lib/tarkovHomeNav";

export default function TarkovHideoutDetailPage() {
  const { stationSlug = "" } = useParams<{ stationSlug: string }>();
  const label = decodeURIComponent(stationSlug);
  return (
    <TarkovItemsPageShell
      crumbs={label ? [{ label }] : []}
      sectionLabel="藏身处"
      sectionHref={TARKOV_HIDEOUT_PATH}
      title={label || "藏身处"}
    >
      <TarkovHideoutPanel wiki stationSlug={stationSlug} />
    </TarkovItemsPageShell>
  );
}
