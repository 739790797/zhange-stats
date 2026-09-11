import { Suspense, lazy } from "react";
import { Navigate, useParams, useSearchParams } from "react-router-dom";
import { TarkovItemBrowseLayout } from "@/components/guides/tarkov/TarkovItemCatalogPanel";
import { TarkovItemsPageShell } from "@/components/guides/tarkov/TarkovItemsPageShell";
import { PanelFallback } from "@/components/RouteFallback";
import { TARKOV_HOME_PATH } from "@/lib/tarkovHomeNav";
import { weaponClassesForHandbookChildId } from "@/lib/tarkovGunCategories";
import {
  catalogPageForBrowse,
  findHandbookChild,
  handbookHref,
  handbookRootBySlug,
  itemBrowseKind,
  ITEMS_BASE_PATH,
  itemPageBySlug,
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
  const [searchParams, setSearchParams] = useSearchParams();
  const page = itemPageBySlug(typeSegment);
  const childParam = (searchParams.get("child") || "").trim();
  const activeChild = page
    ? findHandbookChild(page.children, childParam) || null
    : null;

  const setChild = (id: string | null) => {
    const next = new URLSearchParams(searchParams);
    if (id) next.set("child", id);
    else next.delete("child");
    next.delete("page");
    next.delete("rig");
    next.delete("sort");
    next.delete("dir");
    setSearchParams(next, { replace: true });
  };

  if (!page) {
    return <Navigate to={TARKOV_HOME_PATH} replace />;
  }

  if (page.parentSlug) {
    const parent = handbookRootBySlug(page.parentSlug);
    if (!parent) {
      return <Navigate to={TARKOV_HOME_PATH} replace />;
    }
    const next = new URLSearchParams(searchParams);
    const childId = page.categoryIds[0];
    if (childId && !next.get("child")) next.set("child", childId);
    const qs = next.toString();
    return (
      <Navigate to={`${handbookHref(parent)}${qs ? `?${qs}` : ""}`} replace />
    );
  }

  const kind = itemBrowseKind(page, activeChild);
  const catalogPage = catalogPageForBrowse(page, activeChild);
  const weaponClasses = weaponClassesForHandbookChildId(activeChild?.id);

  const catalog = (
    <Suspense fallback={<PanelFallback tip="加载物品…" />}>
      <TarkovItemCatalogPanel
        key={`${catalogPage.slug}:${activeChild?.id || "all"}`}
        page={catalogPage}
      />
    </Suspense>
  );

  let main = catalog;
  if (kind === "ammo") {
    main = (
      <Suspense fallback={<PanelFallback tip="加载图表…" />}>
        <TarkovAmmoScatterPanel />
      </Suspense>
    );
  } else if (kind === "guns") {
    main = (
      <Suspense fallback={<PanelFallback tip="加载枪械…" />}>
        <TarkovGunsPanel weaponClasses={weaponClasses} />
      </Suspense>
    );
  }

  const body =
    page.panel === "ammo" || page.panel === "guns" ? (
      <TarkovItemBrowseLayout
        nodes={page.children}
        activeId={activeChild?.id ?? null}
        onSelect={setChild}
        main={main}
      />
    ) : (
      catalog
    );

  return (
    <TarkovItemsPageShell
      title={page.label}
      crumbs={[{ label: page.label }]}
      sectionHref={ITEMS_BASE_PATH}
    >
      {body}
    </TarkovItemsPageShell>
  );
}
