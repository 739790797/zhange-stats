import { Spin } from "antd";
import { NestedSpin } from "@/shared/ui/NestedSpin";

export function PanelFallback({ tip }: { tip?: string }) {
  return (
    <div style={{ textAlign: "center", padding: 48 }}>
      {tip ? <NestedSpin tip={tip} /> : <Spin />}
    </div>
  );
}
