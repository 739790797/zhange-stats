import { Tabs } from "antd";
import { Outlet, useLocation, useNavigate } from "react-router-dom";
import { PageHeader } from "@/components/PageHeader";

type AdminTab = { key: string; label: string };

type AdminTabGroup = {
  key: string;
  label: string;
  items: AdminTab[];
};

const TAB_GROUPS: AdminTabGroup[] = [
  {
    key: "users",
    label: "用户与权限",
    items: [
      { key: "/settings/users", label: "用户管理" },
      { key: "/settings/auth", label: "安全设置" },
    ],
  },
  {
    key: "integrations",
    label: "集成",
    items: [
      { key: "/settings/integrations", label: "集成密钥" },
      { key: "/settings/qq-groups", label: "QQ群" },
      { key: "/settings/email", label: "邮箱设置" },
    ],
  },
  {
    key: "ops",
    label: "任务与运维",
    items: [
      { key: "/settings/task-config", label: "任务配置" },
      { key: "/settings/jobs", label: "任务调度" },
      { key: "/settings/update", label: "系统更新" },
    ],
  },
];

const ALL_TABS = TAB_GROUPS.flatMap((g) => g.items);

function groupForPath(pathname: string): AdminTabGroup {
  for (const group of TAB_GROUPS) {
    if (group.items.some((item) => pathname.startsWith(item.key))) {
      return group;
    }
  }
  return TAB_GROUPS[0];
}

export default function SystemAdminPage() {
  const location = useLocation();
  const navigate = useNavigate();

  const activeGroup = groupForPath(location.pathname);
  const activeKey =
    ALL_TABS.find((item) => location.pathname.startsWith(item.key))?.key ||
    "/settings/users";

  return (
    <div>
      <PageHeader title="系统管理" />
      <Tabs
        activeKey={activeGroup.key}
        onChange={(key) => {
          const group = TAB_GROUPS.find((g) => g.key === key);
          if (!group) return;
          const stillInGroup = group.items.some((item) =>
            location.pathname.startsWith(item.key),
          );
          if (!stillInGroup) {
            navigate(group.items[0].key);
          }
        }}
        items={TAB_GROUPS.map((group) => ({
          key: group.key,
          label: group.label,
        }))}
        style={{ marginBottom: 0 }}
      />
      <Tabs
        activeKey={activeKey}
        onChange={(key) => navigate(key)}
        items={activeGroup.items.map((item) => ({
          key: item.key,
          label: item.label,
        }))}
        style={{ marginBottom: 8 }}
      />
      <Outlet />
    </div>
  );
}
