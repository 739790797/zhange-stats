import { Spin } from "antd";
import { Suspense, lazy, useMemo, type ReactNode } from "react";
import { GuideTabsPage } from "@/components/guides/GuideTabsPage";

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

/** 预热懒加载 chunk，避免点 tab 才开始拉 charts 依赖 */
void import("@/components/guides/tarkov/TarkovAmmoScatterPanel");
void import("@/components/guides/tarkov/TarkovGunsPanel");

type TabKey = "ammo" | "guns";

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
      {
        key: "guns",
        label: "枪械",
        children: (
          <Suspense
            fallback={
              <div style={{ padding: 48, textAlign: "center" }}>
                <Spin tip="加载枪械…" />
              </div>
            }
          >
            <TarkovGunsPanel />
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
