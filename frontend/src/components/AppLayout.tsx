import {
  CalendarOutlined,
  KeyOutlined,
  LockOutlined,
  LogoutOutlined,
  MailOutlined,
  ScheduleOutlined,
  SettingOutlined,
  TeamOutlined,
  UserOutlined,
  UsergroupAddOutlined,
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
import { fetchMe, fetchMyProfile, fetchPlatformFeaturesEffective } from "@/api/client";
import { AppVersion } from "@/components/AppVersion";
import { BrandLogo } from "@/components/BrandLogo";
import {
  CompleteProfileModal,
  shouldPromptCompleteProfile,
} from "@/components/CompleteProfileModal";
import { PlatformIcon } from "@/components/PlatformIcon";
import { isAdminUser } from "@/lib/isAdminUser";
import {
  PLATFORM_NAV,
  firstEnabledPlatformPath,
  isFeatureOn,
} from "@/lib/platformFeatures";
import { useAuthStore } from "@/stores/authStore";

const { Header, Sider, Content } = Layout;

const ADMIN_NAV = [
  {
    key: "/settings/users",
    label: "用户管理",
    icon: <TeamOutlined />,
  },
  {
    key: "/settings/auth",
    label: "安全设置",
    icon: <LockOutlined />,
  },
  {
    key: "/settings/integrations",
    label: "集成密钥",
    icon: <KeyOutlined />,
  },
  {
    key: "/settings/qq-groups",
    label: "QQ群",
    icon: <UsergroupAddOutlined />,
  },
  {
    key: "/settings/email",
    label: "邮箱设置",
    icon: <MailOutlined />,
  },
  {
    key: "/settings/task-config",
    label: "任务配置",
    icon: <SettingOutlined />,
  },
  {
    key: "/settings/jobs",
    label: "任务调度",
    icon: <ScheduleOutlined />,
  },
] as const;

const leafKeys = [
  ...ADMIN_NAV.map((item) => item.key),
  "/steam",
  "/skland",
  "/taygedo",
  "/exilium",
  "/kujiequ",
  "/daily",
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

  const featuresQuery = useQuery({
    queryKey: ["platform-features-effective"],
    queryFn: fetchPlatformFeaturesEffective,
    staleTime: 30_000,
  });

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
    // 等 /auth/me 返回后再判断，避免 zustand 水合 / 首屏时 email 暂空误弹「完善账号」
    if (!meQuery.isSuccess) {
      return;
    }
    const state = location.state as { promptCompleteProfile?: boolean } | null;
    const force = Boolean(state?.promptCompleteProfile);
    if (force) {
      navigate(location.pathname, { replace: true, state: {} });
    }
    const email = meQuery.data.email ?? user?.email ?? null;
    if (email) {
      setCompleteOpen(false);
      return;
    }
    if (force || shouldPromptCompleteProfile(email)) {
      setCompleteOpen(true);
    }
  }, [
    location.pathname,
    location.state,
    meQuery.data,
    meQuery.isSuccess,
    navigate,
    user?.email,
  ]);

  const selected = useMemo(() => {
    if (/^\/members\/\d+\/profile/.test(location.pathname)) {
      return "/settings/users";
    }
    if (location.pathname.startsWith("/settings/")) {
      const hit = ADMIN_NAV.find(
        (item) =>
          location.pathname === item.key ||
          location.pathname.startsWith(`${item.key}/`),
      );
      if (hit) return hit.key;
    }
    if (location.pathname.startsWith("/profile")) return "/profile";
    if (location.pathname.startsWith("/daily")) return "/daily";
    if (location.pathname.startsWith("/kujiequ")) return "/kujiequ";
    if (location.pathname.startsWith("/exilium")) return "/exilium";
    if (location.pathname.startsWith("/taygedo")) return "/taygedo";
    if (location.pathname.startsWith("/skland")) return "/skland";
    return (
      leafKeys.find((key) =>
        key === "/steam"
          ? location.pathname === "/steam" ||
            location.pathname === "/" ||
            (location.pathname.startsWith("/members") &&
              !location.pathname.endsWith("/profile"))
          : location.pathname.startsWith(key),
      ) || "/steam"
    );
  }, [location.pathname]);

  const isAdmin = isAdminUser(user);
  const features = featuresQuery.data;

  const platformItems = PLATFORM_NAV.filter((item) =>
    isFeatureOn(features, item.featureId),
  ).map((item) => ({
    key: item.path,
    icon: <PlatformIcon name={item.icon} />,
    label: <Link to={item.path}>{item.label}</Link>,
  }));

  const mineItems = [
    {
      key: "/daily",
      icon: <CalendarOutlined />,
      label: <Link to="/daily">我的日常</Link>,
    },
    {
      key: "/profile",
      icon: <UserOutlined />,
      label: <Link to="/profile">个人中心</Link>,
    },
  ];

  const adminItems = isAdmin
    ? ADMIN_NAV.map((item) => ({
        key: item.key,
        icon: item.icon,
        label: <Link to={item.key}>{item.label}</Link>,
      }))
    : [];

  const menuItems = [
    ...(platformItems.length
      ? [{ type: "group" as const, label: "平台", children: platformItems }]
      : []),
    { type: "group" as const, label: "我的", children: mineItems },
    ...(adminItems.length
      ? [{ type: "group" as const, label: "管理", children: adminItems }]
      : []),
  ];

  useEffect(() => {
    if (featuresQuery.isLoading) return;
    if (/^\/members\/\d+\/profile/.test(location.pathname)) return;
    const hit = PLATFORM_NAV.find(
      (item) =>
        location.pathname === item.path ||
        location.pathname.startsWith(`${item.path}/`) ||
        (item.path === "/steam" &&
          location.pathname.startsWith("/members") &&
          !location.pathname.endsWith("/profile")),
    );
    if (!hit) return;
    if (
      featuresQuery.isError ||
      !isFeatureOn(features, hit.featureId)
    ) {
      navigate(
        firstEnabledPlatformPath(featuresQuery.isError ? null : features),
        { replace: true },
      );
    }
  }, [
    features,
    featuresQuery.isError,
    featuresQuery.isLoading,
    location.pathname,
    navigate,
  ]);

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
            items={menuItems}
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
