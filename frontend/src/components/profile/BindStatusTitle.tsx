import { Tag, Typography } from "antd";
import type { ReactNode } from "react";

/** 绑定行标题：名称定宽，状态标签纵向对齐 */
export function BindStatusTitle({
  name,
  bound,
  leading,
}: {
  name: string;
  bound: boolean;
  leading?: ReactNode;
}) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      {leading}
      <Typography.Text
        strong
        style={{ width: "3.75em", flex: "0 0 3.75em", lineHeight: "22px" }}
      >
        {name}
      </Typography.Text>
      {bound ? <Tag color="success">已绑定</Tag> : <Tag>未绑定</Tag>}
    </div>
  );
}
