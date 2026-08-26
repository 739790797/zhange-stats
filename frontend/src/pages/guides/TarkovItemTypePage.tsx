import { Suspense, lazy } from "react";
import { Navigate, useParams } from "react-router-dom";
import { TarkovItemsPageShell } from "@/components/guides/tarkov/TarkovItemsPageShell";
import { PanelFallback } from "@/components/RouteFallback";
import { TARKOV_HOME_PATH } from "@/lib/tarkovHomeNav";
import {
  handbookHref,
  handbookRootBySlug,
  itemPageBySlug,
  ITEMS_BASE_PATH,
} from "@/lib/tarkovItemTypes";

const TarkovAmmoScatterPanel = lazy(() =>
  import("@/components/guides/tarkov/TarkovAmmoScatterPanel").then((m) => ({
    default: m.TarkovAmmoScatterPanel,
  })),
);

const TarkovGunsPanel = lazy(() =>
  import("@/components/guides/tarkov/TarkovGunsPanel").then((m) => ({
    default: m.TarkovGunsPanel,
  })),
);

const TarkovItemCatalogPanel = lazy(() =>
  import("@/components/guides/tarkov/TarkovItemCatalogPanel").then((m) => ({
    default: m.TarkovItemCatalogPanel,
  })),
);

export default function TarkovItemTypePage() {
  const { typeSegment } = useParams<{ typeSegment: string }>();
  const page = itemPageBySlug(typeSegment);

  if (!page) {
    return <Navigate to={TARKOV_HOME_PATH} replace />;
  }

  const parent = page.parentSlug
    ? handbookRootBySlug(page.parentSlug)
    : undefined;
  const crumbs = [
    ...(parent ? [{ label: parent.label, to: handbookHref(parent) }] : []),
    { label: page.label },
  ];

  return (
    <TarkovItemsPageShell
      title={page.label}
      crumbs={crumbs}
      sectionHref={ITEMS_BASE_PATH}
    >
      {page.panel === "ammo" ? (
        <Suspense fallback={<PanelFallback tip="加载图表…" />}>
          <TarkovAmmoScatterPanel />
        </Suspense>
      ) : page.panel === "guns" ? (
        <Suspense fallback={<PanelFallback tip="加载枪械…" />}>
          <TarkovGunsPanel />
        </Suspense>
      ) : (
        <Suspense fallback={<PanelFallback tip="加载物品…" />}>
          <TarkovItemCatalogPanel key={page.slug} page={page} />
        </Suspense>
      )}
    </TarkovItemsPageShell>
  );
}
