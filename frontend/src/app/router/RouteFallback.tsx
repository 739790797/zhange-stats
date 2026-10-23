import { Spin } from "antd";

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
