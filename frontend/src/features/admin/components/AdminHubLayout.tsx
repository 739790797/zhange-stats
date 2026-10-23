import { Tabs, Typography } from "antd";
import { useMemo, type ReactNode } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { AdminHubEmbeddedContext } from "@/features/admin/components/adminHubContext";
import { adminHubByPath, adminHubTabPath } from "@/features/admin/model/adminHub";

/** 管理端统一外壳：四个入口都走这里，宽度由 AppLayout 的 wide shell 决定。 */
export function AdminHubLayout({ children }: { children: ReactNode }) {
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
    return <>{children}</>;
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
      {children}
    </AdminHubEmbeddedContext.Provider>
  );
}
