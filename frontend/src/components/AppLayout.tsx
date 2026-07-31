import {
  CalendarOutlined,
  CloudDownloadOutlined,
  LogoutOutlined,
  SettingOutlined,
  TeamOutlined,
  UserOutlined,
} from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import {
  Avatar,
  Dropdown,
  Layout,
  Menu,
  Tag,
  Typography,
  theme,
  type MenuProps,
} from "antd";
import { useEffect, useMemo } from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { fetchMe, fetchMyProfile } from "@/api/client";
import { SiteFooter } from "@/components/SiteFooter";
import { useAuthStore } from "@/stores/authStore";

const { Header, Sider, Content } = Layout;

const leafKeys = ["/steam", "/friends"];

export function AppLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const setUser = useAuthStore((s) => s.setUser);
  const logout = useAuthStore((s) => s.logout);
  const { token } = theme.useToken();

  const meQuery = useQuery({
    queryKey: ["auth-me"],
    queryFn: fetchMe,
  });

  const profileQuery = useQuery({
    queryKey: ["profile-me"],
    queryFn: fetchMyProfile,
  });

  useEffect(() => {
    if (!meQuery.data) return;
    setUser(meQuery.data);
  }, [meQuery.data, setUser]);

  useEffect(() => {
    const profile = profileQuery.data;
    if (!profile) return;
    const current = useAuthStore.getState().user;
    if (!current) return;
    const nextName = profile.display_name || profile.nickname;
    const nextAvatar = profile.avatar_url;
    const nextSteam = profile.steam_id ?? null;
    if (
      (nextName && nextName !== current.display_name) ||
      (nextAvatar !== undefined && nextAvatar !== current.avatar_url) ||
      nextSteam !== (current.steam_id ?? null)
    ) {
      setUser({
        ...current,
        display_name: nextName || current.display_name,
        avatar_url: nextAvatar ?? current.avatar_url ?? null,
        steam_id: nextSteam,
      });
    }
  }, [profileQuery.data, setUser]);

  const selected = useMemo(() => {
    if (location.pathname.startsWith("/friends")) return "/friends";
    if (location.pathname.startsWith("/members")) return "/friends";
    return (
      leafKeys.find((key) =>
        key === "/steam"
          ? location.pathname === "/steam" || location.pathname === "/"
          : location.pathname.startsWith(key),
      ) || "/steam"
    );
  }, [location.pathname]);

  const items = [
    {
      key: "/steam",
      icon: <CalendarOutlined />,
      label: <Link to="/steam">今天玩什么</Link>,
    },
    {
      key: "/friends",
      icon: <TeamOutlined />,
      label: <Link to="/friends">好友</Link>,
    },
  ];

  const displayName =
    profileQuery.data?.display_name ||
    profileQuery.data?.nickname ||
    user?.display_name ||
    user?.email ||
    "用户";
  const avatarUrl =
    profileQuery.data?.avatar_url || user?.avatar_url || undefined;
  const isAdmin = Boolean(user?.is_admin);
  const roleLabel = isAdmin ? "管理员" : null;

  const accountMenuItems: MenuProps["items"] = [
    {
      key: "profile",
      icon: <UserOutlined />,
      label: "个人中心",
      onClick: () => navigate("/profile"),
    },
    ...(isAdmin
      ? [
          { type: "divider" as const },
          {
            key: "settings-users",
            icon: <TeamOutlined />,
            label: "用户管理",
            onClick: () => navigate("/settings/users"),
          },
          {
            key: "settings-email",
            icon: <SettingOutlined />,
            label: "邮箱设置",
            onClick: () => navigate("/settings/email"),
          },
          {
            key: "settings-update",
            icon: <CloudDownloadOutlined />,
            label: "系统更新",
            onClick: () => navigate("/settings/update"),
          },
        ]
      : []),
    { type: "divider" as const },
    {
      key: "logout",
      icon: <LogoutOutlined />,
      label: "退出登录",
      danger: true,
      onClick: () => {
        logout();
        navigate("/login");
      },
    },
  ];

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider
        breakpoint="lg"
        collapsedWidth={64}
        width={220}
        style={{
          background: "#1a2332",
          height: "100vh",
          position: "sticky",
          top: 0,
          left: 0,
          overflow: "hidden",
        }}
      >
        <div
          style={{
            height: "100%",
            display: "flex",
            flexDirection: "column",
            overflow: "hidden",
          }}
        >
          <div
            style={{
              height: 64,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              borderBottom: "1px solid rgba(255,255,255,0.08)",
              flexShrink: 0,
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
            items={items}
            style={{
              background: "#1a2332",
              borderInlineEnd: "none",
              flex: 1,
              minHeight: 0,
              overflowY: "auto",
              paddingTop: 8,
            }}
          />
          <div
            style={{
              borderTop: "1px solid rgba(255,255,255,0.08)",
              padding: "12px 10px",
              flexShrink: 0,
            }}
          >
            <Dropdown
              menu={{ items: accountMenuItems }}
              trigger={["click"]}
              placement="topLeft"
            >
              <button
                type="button"
                style={{
                  width: "100%",
                  display: "flex",
                  alignItems: "center",
                  gap: 10,
                  padding: "8px 10px",
                  border: "none",
                  borderRadius: 8,
                  background: "transparent",
                  cursor: "pointer",
                  textAlign: "left",
                  color: "#fff",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = "rgba(255,255,255,0.06)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = "transparent";
                }}
              >
                <Avatar size={36} src={avatarUrl}>
                  {displayName?.[0] || "?"}
                </Avatar>
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div
                    style={{
                      color: "#fff",
                      fontWeight: 600,
                      fontSize: 14,
                      lineHeight: 1.3,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {displayName}
                  </div>
                  {roleLabel ? (
                    <Tag
                      style={{
                        marginTop: 4,
                        marginInlineEnd: 0,
                        fontSize: 11,
                        lineHeight: "18px",
                        borderColor: "rgba(255,255,255,0.2)",
                        background: "rgba(255,255,255,0.06)",
                        color: "rgba(255,255,255,0.75)",
                      }}
                    >
                      {roleLabel}
                    </Tag>
                  ) : null}
                </div>
              </button>
            </Dropdown>
          </div>
        </div>
      </Sider>
      <Layout>
        <Header
          style={{
            background: token.colorBgContainer,
            padding: "0 24px",
            height: 56,
            lineHeight: "56px",
            borderBottom: `1px solid ${token.colorBorderSecondary}`,
          }}
        />
        <Content
          style={{
            margin: 24,
            display: "flex",
            flexDirection: "column",
            minHeight: "calc(100vh - 56px - 48px)",
          }}
        >
          <div
            style={{
              background: token.colorBgContainer,
              padding: 24,
              borderRadius: 8,
              minHeight: 360,
              flex: 1,
            }}
          >
            <Outlet />
          </div>
          <SiteFooter />
        </Content>
      </Layout>
    </Layout>
  );
}
