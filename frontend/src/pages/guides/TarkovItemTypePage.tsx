import { Button, Result, Spin } from "antd";
import { Suspense, lazy } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import { TarkovItemsPageShell } from "@/components/guides/tarkov/TarkovItemsPageShell";
import {
  ITEMS_BASE_PATH,
  handbookRootBySlug,
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

void import("@/components/guides/tarkov/TarkovAmmoScatterPanel");
void import("@/components/guides/tarkov/TarkovGunsPanel");

function PanelFallback({ tip }: { tip: string }) {
  return (
    <div style={{ padding: 48, textAlign: "center" }}>
      <Spin tip={tip} />
    </div>
  );
}

export default function TarkovItemTypePage() {
  const navigate = useNavigate();
  const { typeSegment } = useParams<{ typeSegment: string }>();
  const root = handbookRootBySlug(typeSegment);

  if (!root) {
    return <Navigate to={ITEMS_BASE_PATH} replace />;
  }

  return (
    <TarkovItemsPageShell title={root.label} crumbs={[{ label: root.label }]}>
      {root.panel === "ammo" ? (
        <Suspense fallback={<PanelFallback tip="加载图表…" />}>
          <TarkovAmmoScatterPanel />
        </Suspense>
      ) : root.panel === "guns" ? (
        <Suspense fallback={<PanelFallback tip="加载枪械…" />}>
          <TarkovGunsPanel />
        </Suspense>
      ) : (
        <Result
          status="info"
          title="即将推出"
          subTitle={`${root.label}数据尚未接入，敬请期待。`}
          extra={
            <Button type="primary" onClick={() => navigate(ITEMS_BASE_PATH)}>
              返回分类
            </Button>
          }
        />
      )}
    </TarkovItemsPageShell>
  );
}
