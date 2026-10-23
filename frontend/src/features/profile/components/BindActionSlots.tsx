import type { CSSProperties, ReactNode } from "react";

/** 绑定行操作区：三列定宽，跨行纵向对齐（解绑 | 角色 | 换绑/绑定） */
const gridStyle: CSSProperties = {
  display: "grid",
  // 列宽覆盖「重新绑定」四字按钮，空位仍占位以跨行对齐
  gridTemplateColumns: "7em 7em 7em",
  gap: 8,
  flex: "0 0 auto",
  justifyItems: "stretch",
};

export function BindActionSlots({
  roles,
  primary,
  danger,
}: {
  roles?: ReactNode;
  primary: ReactNode;
  danger?: ReactNode;
}) {
  return (
    <div style={gridStyle}>
      <div>{danger ?? null}</div>
      <div>{roles ?? null}</div>
      <div>{primary}</div>
    </div>
  );
}
