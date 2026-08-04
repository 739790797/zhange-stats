import {
  ControlOutlined,
  LogoutOutlined,
  UserOutlined,
} from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import {
  Avatar,
  Button,
  Layout,
  Menu,
  Tag,
  Tooltip,
  Typography,
  theme,
} from "antd";
import { useEffect, useMemo, useState } from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { fetchMe, fetchMyProfile } from "@/api/client";
import { AppVersion } from "@/components/AppVersion";
import { BrandLogo } from "@/components/BrandLogo";
import {
  CompleteProfileModal,
  shouldPromptCompleteProfile,
} from "@/components/CompleteProfileModal";
import { PlatformIcon } from "@/components/PlatformIcon";
import { useAuthStore } from "@/stores/authStore";

const { Header, Sider, Content } = Layout;

const leafKeys = [
  "/settings",
  "/steam",
  "/skland",
  "/taygedo",
  "/exilium",
  "/kujiequ",
  "/profile",
];

export function AppLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const setUser = useAuthStore((s) => s.setUser);
  const logout = useAuthStore((s) => s.logout);
  const { token } = theme.useToken();
  const [completeOpen, setCompleteOpen] = useState(false);

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

  useEffect(() => {
    const state = location.state as { promptCompleteProfile?: boolean } | null;
    const force = Boolean(state?.promptCompleteProfile);
    if (force) {
      navigate(location.pathname, { replace: true, state: {} });
    }
    const email = meQuery.data?.email ?? user?.email;
    if (force || shouldPromptCompleteProfile(email)) {
      if (!email) setCompleteOpen(true);
    }
  }, [
    location.pathname,
    location.state,
    meQuery.data?.email,
    navigate,
    user?.email,
  ]);

  const selected = useMemo(() => {
    if (location.pathname.startsWith("/settings")) return "/settings";
    if (location.pathname.startsWith("/profile")) return "/profile";
    if (location.pathname.startsWith("/kujiequ")) return "/kujiequ";
    if (location.pathname.startsWith("/exilium")) return "/exilium";
    if (location.pathname.startsWith("/taygedo")) return "/taygedo";
    if (location.pathname.startsWith("/skland")) return "/skland";
    return (
      leafKeys.find((key) =>
        key === "/steam"
          ? location.pathname === "/steam" ||
            location.pathname === "/" ||
            location.pathname.startsWith("/members")
          : location.pathname.startsWith(key),
      ) || "/steam"
    );
  }, [location.pathname]);

  const isAdmin = Boolean(user?.is_admin);

  const items = [
    {
      key: "/steam",
      icon: <PlatformIcon name="steam" />,
      label: <Link to="/steam">Steam</Link>,
    },
    {
      key: "/skland",
      icon: <PlatformIcon name="skland" />,
      label: <Link to="/skland">森空岛</Link>,
    },
    {
      key: "/taygedo",
      icon: <PlatformIcon name="taygedo" />,
      label: <Link to="/taygedo">塔吉多</Link>,
    },
    {
      key: "/exilium",
      icon: <PlatformIcon name="exilium" />,
      label: <Link to="/exilium">追放</Link>,
    },
    {
      key: "/kujiequ",
      icon: <PlatformIcon name="kujiequ" />,
      label: <Link to="/kujiequ">库街区</Link>,
    },
  ];

  const bottomItems = [
    ...(isAdmin
      ? [
          {
            key: "/settings",
            icon: <ControlOutlined />,
            label: <Link to="/settings/users">系统管理</Link>,
          },
        ]
      : []),
    {
      key: "/profile",
      icon: <UserOutlined />,
      label: <Link to="/profile">个人中心</Link>,
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
  const roleLabel = isAdmin ? "管理员" : null;

  const onLogout = () => {
    logout();
    navigate("/login");
  };

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
              gap: 8,
              borderBottom: "1px solid rgba(255,255,255,0.08)",
              flexShrink: 0,
            }}
          >
            <BrandLogo size={32} color="#e8b86d" />
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
              flexShrink: 0,
            }}
          >
            <Menu
              theme="dark"
              mode="inline"
              className="sider-menu"
              selectedKeys={
                selected === "/profile" || selected === "/settings"
                  ? [selected]
                  : []
              }
              items={bottomItems}
              style={{
                background: "#1a2332",
                borderInlineEnd: "none",
              }}
            />
            <div style={{ padding: "4px 10px 12px" }}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "8px 10px",
                  borderRadius: 8,
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
                <Tooltip title="退出登录">
                  <Button
                    type="text"
                    className="sider-logout-btn"
                    icon={<LogoutOutlined />}
                    aria-label="退出登录"
                    onClick={onLogout}
                  />
                </Tooltip>
              </div>
              <div style={{ marginTop: 4, paddingBottom: 2 }}>
                <AppVersion light />
              </div>
            </div>
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
      <CompleteProfileModal
        open={completeOpen}
        onClose={() => setCompleteOpen(false)}
        onCompleted={() => {
          setCompleteOpen(false);
          meQuery.refetch();
          profileQuery.refetch();
        }}
      />
    </Layout>
  );
}
