import { Spin } from "antd";
import { Suspense, lazy } from "react";
import { PageHeader } from "@/components/PageHeader";

const TarkovGunsPanel = lazy(() =>
  import("@/components/guides/tarkov/TarkovGunsPanel").then((m) => ({
    default: m.TarkovGunsPanel,
  })),
);

void import("@/components/guides/tarkov/TarkovGunsPanel");

export default function TarkovGunsPage() {
  return (
    <div>
      <PageHeader title="枪械" subtitle="逃离塔科夫 · 物品" />
      <Suspense
        fallback={
          <div style={{ padding: 48, textAlign: "center" }}>
            <Spin tip="加载枪械…" />
          </div>
        }
      >
        <TarkovGunsPanel />
      </Suspense>
    </div>
  );
}
