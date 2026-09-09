import { Spin } from "antd";

/** antd 5：`tip` 必须包一层子节点，否则不显示且控制台警告。 */
export function NestedSpin({
  tip,
  minHeight = 48,
}: {
  tip: string;
  minHeight?: number;
}) {
  return (
    <Spin tip={tip}>
      <div style={{ minHeight }} />
    </Spin>
  );
}
