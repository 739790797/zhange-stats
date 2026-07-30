import {
  DashboardOutlined,
  FormOutlined,
  SettingOutlined,
  TeamOutlined,
  TrophyOutlined,
  LogoutOutlined,
} from "@ant-design/icons";
import { Layout, Menu, Typography, Button, Space, theme } from "antd";
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
    key: "/records/new",
    icon: <FormOutlined />,
    label: <Link to="/records/new">战绩录入</Link>,
  },
  {
    key: "/leaderboard",
    icon: <TrophyOutlined />,
    label: <Link to="/leaderboard">排行榜</Link>,
  },
];

export function AppLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const { token } = theme.useToken();

  const selected = menuItems
    .map((i) => i.key)
    .concat(["/settings"])
    .find((key) =>
      key === "/"
        ? location.pathname === "/"
        : location.pathname.startsWith(key),
    );

  const items = [
    ...menuItems,
    ...(user?.is_admin
      ? [
          {
            key: "/settings",
            icon: <SettingOutlined />,
            label: <Link to="/settings">系统设置</Link>,
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
            圈子战绩
          </Typography.Text>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selected || "/"]}
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
            <Typography.Text>{user?.display_name || user?.username}</Typography.Text>
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
