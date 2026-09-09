import { Spin } from "antd";
import { NestedSpin } from "@/components/NestedSpin";

export function RouteFallback() {
  return (
    <div
      style={{
        minHeight: 240,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 48,
      }}
    >
      <Spin />
    </div>
  );
}

export function PanelFallback({ tip }: { tip?: string }) {
  return (
    <div style={{ textAlign: "center", padding: 48 }}>
      {tip ? <NestedSpin tip={tip} /> : <Spin />}
    </div>
  );
}
