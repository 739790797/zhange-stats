import { Spin } from "antd";
import { Suspense, lazy } from "react";
import { PageHeader } from "@/components/PageHeader";

const TarkovAmmoScatterPanel = lazy(() =>
  import("@/components/guides/tarkov/TarkovAmmoScatterPanel").then((m) => ({
    default: m.TarkovAmmoScatterPanel,
  })),
);

void import("@/components/guides/tarkov/TarkovAmmoScatterPanel");

export default function TarkovAmmoPage() {
  return (
    <div>
      <PageHeader title="弹药" subtitle="逃离塔科夫 · 物品" />
      <Suspense
        fallback={
          <div style={{ padding: 48, textAlign: "center" }}>
            <Spin tip="加载图表…" />
          </div>
        }
      >
        <TarkovAmmoScatterPanel />
      </Suspense>
    </div>
  );
}
