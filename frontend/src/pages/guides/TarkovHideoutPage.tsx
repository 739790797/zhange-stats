import { TarkovHideoutPanel } from "@/components/guides/tarkov/TarkovHideoutPanel";
import { TarkovItemsPageShell } from "@/components/guides/tarkov/TarkovItemsPageShell";

export default function TarkovHideoutPage() {
  return (
    <TarkovItemsPageShell crumbs={[]} sectionLabel="藏身处" title="藏身处">
      <TarkovHideoutPanel wiki />
    </TarkovItemsPageShell>
  );
}
