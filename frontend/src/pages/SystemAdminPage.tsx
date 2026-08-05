import { Tabs } from "antd";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { PageHeader } from "@/components/PageHeader";

const TAB_ITEMS = [
  { key: "/settings/users", label: "用户管理" },
  { key: "/settings/integrations", label: "集成密钥" },
  { key: "/settings/qq-groups", label: "QQ群" },
  { key: "/settings/auth", label: "安全设置" },
  { key: "/settings/email", label: "邮箱设置" },
  { key: "/settings/task-config", label: "任务配置" },
  { key: "/settings/jobs", label: "任务调度" },
  { key: "/settings/update", label: "系统更新" },
];

export default function SystemAdminPage() {
  const location = useLocation();
  const navigate = useNavigate();

  const activeKey =
    TAB_ITEMS.find((item) => location.pathname.startsWith(item.key))?.key ||
    "/settings/users";

  return (
    <div>
      <PageHeader title="系统管理" />
      <Tabs
        activeKey={activeKey}
        onChange={(key) => navigate(key)}
        items={TAB_ITEMS.map((item) => ({
          key: item.key,
          label: item.label,
        }))}
        style={{ marginBottom: 8 }}
      />
      <Outlet />
    </div>
  );
}
