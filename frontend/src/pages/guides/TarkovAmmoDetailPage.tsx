import { useParams } from "react-router-dom";
import {
  TarkovAmmoDetailPanel,
  useTarkovAmmoDetailTitle,
} from "@/components/guides/tarkov/TarkovAmmoDetailPanel";
import { TarkovItemsPageShell } from "@/components/guides/tarkov/TarkovItemsPageShell";
import { itemTypeHref } from "@/lib/tarkovItemTypes";

export default function TarkovAmmoDetailPage() {
  const { itemId = "" } = useParams<{ itemId: string }>();
  const title = useTarkovAmmoDetailTitle(itemId);

  return (
    <TarkovItemsPageShell
      title={title}
      crumbs={[
        { label: "弹药", to: itemTypeHref("ammo") },
        { label: title },
      ]}
    >
      {itemId ? <TarkovAmmoDetailPanel itemId={itemId} /> : null}
    </TarkovItemsPageShell>
  );
}
