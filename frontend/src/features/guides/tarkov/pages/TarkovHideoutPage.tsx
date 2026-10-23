import { TarkovHideoutPanel } from "@/features/guides/tarkov/components/TarkovHideoutPanel";
import { TarkovItemsPageShell } from "@/features/guides/tarkov/components/TarkovItemsPageShell";

export default function TarkovHideoutPage() {
  return (
    <TarkovItemsPageShell crumbs={[]} sectionLabel="藏身处" title="藏身处">
      <TarkovHideoutPanel wiki />
    </TarkovItemsPageShell>
  );
}
