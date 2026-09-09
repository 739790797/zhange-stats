import { Tabs, Typography } from "antd";
import { Suspense, useMemo } from "react";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { AdminHubEmbeddedContext } from "@/components/adminHubContext";
import { PageMotion } from "@/components/PageMotion";
import { RouteErrorBoundary } from "@/components/RouteErrorBoundary";
import { PanelFallback } from "@/components/RouteFallback";
import { adminHubByPath, adminHubTabPath } from "@/lib/adminHub";

/**
 * 管理端统一外壳：四个入口都走这里，宽度由 AppLayout 的 wide shell 决定。
 * 多于一个 Tab 时才画导航条；子页走 Outlet（各自保存 / 步进验证码 / 轮询互不常驻）。
 */
export function AdminHubLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const hub = adminHubByPath(location.pathname);
  const activeKey = adminHubTabPath(location.pathname);
  const showTabs = (hub?.tabs.length ?? 0) > 1;

  const items = useMemo(
    () => (hub ? hub.tabs.map((tab) => ({ key: tab.path, label: tab.label })) : []),
    [hub],
  );

  if (!hub || !activeKey) {
    return <Outlet />;
  }

  return (
    <AdminHubEmbeddedContext.Provider value={true}>
      <Typography.Title level={3} style={{ margin: "0 0 8px" }}>
        {hub.label}
      </Typography.Title>
      {showTabs ? (
        <Tabs
          className="admin-hub-tabs"
          activeKey={activeKey}
          onChange={(key) => navigate(key)}
          items={items}
        />
      ) : null}
      <Suspense fallback={<PanelFallback />}>
        <RouteErrorBoundary resetKey={location.pathname}>
          <PageMotion motionKey={location.pathname}>
            <Outlet />
          </PageMotion>
        </RouteErrorBoundary>
      </Suspense>
    </AdminHubEmbeddedContext.Provider>
  );
}
