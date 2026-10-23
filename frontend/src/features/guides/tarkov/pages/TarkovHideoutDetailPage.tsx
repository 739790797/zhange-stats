import { useParams } from "react-router-dom";
import { TarkovHideoutPanel } from "@/features/guides/tarkov/components/TarkovHideoutPanel";
import { TarkovItemsPageShell } from "@/features/guides/tarkov/components/TarkovItemsPageShell";
import { TARKOV_HIDEOUT_PATH } from "@/features/guides/tarkov/model/tarkovHomeNav";

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
