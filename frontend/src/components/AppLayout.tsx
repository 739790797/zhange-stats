import {
  DashboardOutlined,
  SettingOutlined,
  TeamOutlined,
  LogoutOutlined,
  CalendarOutlined,
  UserOutlined,
  MailOutlined,
} from "@ant-design/icons";
import { Layout, Menu, Typography, Button, Space, theme } from "antd";
import { useEffect, useMemo, useState } from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useAuthStore } from "@/stores/authStore";

const { Header, Sider, Content } = Layout;

const menuItems = [
  { key: "/", icon: <DashboardOutlined />, label: <Link to="/">总览</Link> },
  {
    key: "/members",
    icon: <TeamOutlined />,
    label: <Link to="/members">成员</Link>,
  },
  {
    key: "/steam",
    icon: <CalendarOutlined />,
    label: <Link to="/steam">Steam 日历</Link>,
  },
  {
    key: "/profile",
    icon: <UserOutlined />,
    label: <Link to="/profile">个人设置</Link>,
  },
];

export function AppLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const { token } = theme.useToken();

  const settingsOpen = location.pathname.startsWith("/settings");
  const [openKeys, setOpenKeys] = useState<string[]>(
    settingsOpen ? ["settings"] : [],
  );

  useEffect(() => {
    if (settingsOpen) {
      setOpenKeys((keys) =>
        keys.includes("settings") ? keys : [...keys, "settings"],
      );
    }
  }, [settingsOpen]);

  const selected = useMemo(() => {
    if (location.pathname.startsWith("/settings/email")) return "/settings/email";
    if (location.pathname.startsWith("/settings")) return "/settings/users";
    return (
      menuItems
        .map((i) => i.key)
        .find((key) =>
          key === "/"
            ? location.pathname === "/"
            : location.pathname.startsWith(key),
        ) || "/"
    );
  }, [location.pathname]);

  const items = [
    ...menuItems,
    ...(user?.is_admin
      ? [
          {
            key: "settings",
            icon: <SettingOutlined />,
            label: "系统设置",
            children: [
              {
                key: "/settings/users",
                icon: <TeamOutlined />,
                label: <Link to="/settings/users">用户管理</Link>,
              },
              {
                key: "/settings/email",
                icon: <MailOutlined />,
                label: <Link to="/settings/email">邮箱设置</Link>,
              },
            ],
          },
        ]
      : []),
  ];

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider
        breakpoint="lg"
        collapsedWidth={64}
        style={{ background: "#1a2332" }}
      >
        <div
          style={{
            height: 64,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            borderBottom: "1px solid rgba(255,255,255,0.08)",
          }}
        >
          <Typography.Text
            strong
            style={{ color: "#e8b86d", fontSize: 16, letterSpacing: 1 }}
          >
            战鸽数据
          </Typography.Text>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          className="sider-menu"
          selectedKeys={[selected]}
          openKeys={openKeys}
          onOpenChange={setOpenKeys}
          items={items}
          style={{ background: "#1a2332", borderInlineEnd: "none" }}
        />
      </Sider>
      <Layout>
        <Header
          style={{
            background: token.colorBgContainer,
            padding: "0 24px",
            display: "flex",
            alignItems: "center",
            justifyContent: "flex-end",
            borderBottom: `1px solid ${token.colorBorderSecondary}`,
          }}
        >
          <Space>
            <Typography.Text>{user?.display_name || user?.email}</Typography.Text>
            <Button
              type="text"
              icon={<LogoutOutlined />}
              onClick={() => {
                logout();
                navigate("/login");
              }}
            >
              退出
            </Button>
          </Space>
        </Header>
        <Content style={{ margin: 24 }}>
          <div
            style={{
              background: token.colorBgContainer,
              padding: 24,
              borderRadius: 8,
              minHeight: 360,
            }}
          >
            <Outlet />
          </div>
        </Content>
      </Layout>
    </Layout>
  );
}
