import { Spin } from "antd";
import { Suspense, lazy, useMemo, type ReactNode } from "react";
import { GuideTabsPage } from "@/components/guides/GuideTabsPage";

const TarkovAmmoScatterPanel = lazy(() =>
  import("@/components/guides/tarkov/TarkovAmmoScatterPanel").then((m) => ({
    default: m.TarkovAmmoScatterPanel,
  })),
);

type TabKey = "ammo";

export default function TarkovPage() {
  const tabItems = useMemo(() => {
    const items: { key: TabKey; label: string; children: ReactNode }[] = [
      {
        key: "ammo",
        label: "弹药",
        children: (
          <Suspense
            fallback={
              <div style={{ padding: 48, textAlign: "center" }}>
                <Spin tip="加载图表…" />
              </div>
            }
          >
            <TarkovAmmoScatterPanel />
          </Suspense>
        ),
      },
    ];
    return items;
  }, []);

  return (
    <GuideTabsPage
      title="逃离塔科夫"
      tabItems={tabItems}
      defaultTab="ammo"
    />
  );
}
