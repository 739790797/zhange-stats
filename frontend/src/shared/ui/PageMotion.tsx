import type { ReactNode } from "react";

type PageMotionProps = {
  /** 通常用 pathname；query 变化不要写入，避免筛选重播。 */
  motionKey: string;
  children: ReactNode;
};

/**
 * 路由内容进入淡入。退场不做：Outlet 已卸载，平台 Tab 仍 destroyInactiveTabPane。
 * 用真实包裹盒（不用 display:contents），塔科夫 bodyFill 已按多一层选择器对齐。
 */
export function PageMotion({ motionKey, children }: PageMotionProps) {
  return (
    <div key={motionKey} className="app-motion-page">
      {children}
    </div>
  );
}

type MotionInProps = {
  children: ReactNode;
  className?: string;
};

/** 组件挂载淡入（绑定门禁、空态等非路由切换）。 */
export function MotionIn({ children, className }: MotionInProps) {
  return (
    <div
      className={["app-motion-in", className].filter(Boolean).join(" ")}
    >
      {children}
    </div>
  );
}
