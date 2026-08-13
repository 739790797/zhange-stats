import {
  CalendarOutlined,
  CloudDownloadOutlined,
  FileTextOutlined,
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
import type { MenuProps } from "antd";
import { useEffect, useMemo, useState } from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { fetchAppUpdateStatus } from "@/api/appUpdateApi";
import { fetchMe, fetchMyProfile, fetchPlatformFeaturesEffective } from "@/api/client";
import { AppVersion } from "@/components/AppVersion";
import { BrandLogo } from "@/components/BrandLogo";
import { CompleteProfileModal } from "@/components/CompleteProfileModal";
import { PlatformIcon } from "@/components/PlatformIcon";
import { shouldPromptCompleteProfile } from "@/lib/completeProfile";
import { isAdminUser } from "@/lib/isAdminUser";
import { GUIDE_LEAF_PATHS, GUIDE_NAV, type GuideNavNode } from "@/lib/guideNav";
import {
  PLATFORM_NAV,
  firstEnabledPlatformPath,
  isFeatureOn,
} from "@/lib/platformFeatures";
import { useAuthStore } from "@/stores/authStore";

const { Header, Sider, Content } = Layout;

const SYSTEM_CHILD_KEYS = [
  "/settings/auth",
  "/settings/integrations",
  "/settings/email",
  "/settings/system",
] as const;

const JOBS_CHILD_KEYS = ["/settings/task-config", "/settings/jobs"] as const;

const ADMIN_LEAF_KEYS = [
  "/settings/users",
  "/settings/qq-groups",
  ...JOBS_CHILD_KEYS,
  "/settings/logs",
  ...SYSTEM_CHILD_KEYS,
] as const;

const GUIDE_LEAF_KEYS = GUIDE_LEAF_PATHS;

const leafKeys = [
  ...ADMIN_LEAF_KEYS,
  ...GUIDE_LEAF_KEYS,
  "/steam",
  "/skland",
  "/taygedo",
  "/kujiequ",
  "/exilium",
  "/daily",
  "/profile",
];

function buildAdminMenuItems(): MenuProps["items"] {
  return [
    {
      key: "admin-system",
      icon: <SettingOutlined />,
      label: "系统管理",
      children: [
        {
          key: "/settings/auth",
          icon: <LockOutlined />,
          label: <Link to="/settings/auth">安全设置</Link>,
        },
        {
          key: "/settings/integrations",
          icon: <KeyOutlined />,
          label: <Link to="/settings/integrations">集成密钥</Link>,
        },
        {
          key: "/settings/email",
          icon: <MailOutlined />,
          label: <Link to="/settings/email">邮箱设置</Link>,
        },
        {
          key: "/settings/system",
          icon: <CloudDownloadOutlined />,
          label: <Link to="/settings/system">系统更新</Link>,
        },
      ],
    },
    {
      key: "admin-jobs",
      icon: <ScheduleOutlined />,
      label: "任务管理",
      children: [
        {
          key: "/settings/task-config",
          icon: <SettingOutlined />,
          label: <Link to="/settings/task-config">任务配置</Link>,
        },
        {
          key: "/settings/jobs",
          icon: <ScheduleOutlined />,
          label: <Link to="/settings/jobs">任务调度</Link>,
        },
      ],
    },
    {
      key: "/settings/users",
      icon: <TeamOutlined />,
      label: <Link to="/settings/users">用户管理</Link>,
    },
    {
      key: "/settings/logs",
      icon: <FileTextOutlined />,
      label: <Link to="/settings/logs">平台日志</Link>,
    },
    {
      key: "/settings/qq-groups",
      icon: <UsergroupAddOutlined />,
      label: <Link to="/settings/qq-groups">QQ群</Link>,
    },
  ];
}

export function AppLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const setUser = useAuthStore((s) => s.setUser);
  const logout = useAuthStore((s) => s.logout);
  const { token } = theme.useToken();
  const [completeOpen, setCompleteOpen] = useState(false);
  const [openKeys, setOpenKeys] = useState<string[]>([]);

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
      const hit = ADMIN_LEAF_KEYS.find(
        (key) =>
          location.pathname === key || location.pathname.startsWith(`${key}/`),
      );
      if (hit) return hit;
    }
    if (location.pathname.startsWith("/profile")) return "/profile";
    if (location.pathname.startsWith("/daily")) return "/daily";
    if (location.pathname.startsWith("/guides/")) {
      const hit = GUIDE_LEAF_KEYS.filter(
        (key) =>
          location.pathname === key || location.pathname.startsWith(`${key}/`),
      ).sort((a, b) => b.length - a.length)[0];
      if (hit) return hit;
    }
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

  useEffect(() => {
    const next: string[] = [];
    if ((SYSTEM_CHILD_KEYS as readonly string[]).includes(selected)) {
      next.push("admin-system");
    }
    if ((JOBS_CHILD_KEYS as readonly string[]).includes(selected)) {
      next.push("admin-jobs");
    }
    if (!next.length) return;
    setOpenKeys((prev) => Array.from(new Set([...prev, ...next])));
  }, [selected]);

  const isAdmin = isAdminUser(user);
  const features = featuresQuery.data;

  const appUpdateQuery = useQuery({
    queryKey: ["app-update-status"],
    queryFn: fetchAppUpdateStatus,
    enabled: isAdmin,
    staleTime: 5 * 60_000,
    refetchInterval: 30 * 60_000,
    refetchOnWindowFocus: true,
    retry: 1,
  });
  const hasAppUpdate = Boolean(appUpdateQuery.data?.has_new_version);

  const platformItems = PLATFORM_NAV.filter((item) =>
    isFeatureOn(features, item.featureId),
  ).map((item) => ({
    key: item.path,
    icon: <PlatformIcon name={item.icon} />,
    label: <Link to={item.path}>{item.label}</Link>,
  }));

  const guideItems = useMemo(() => {
    const mapNode = (node: GuideNavNode): NonNullable<MenuProps["items"]>[number] | null => {
      if (node.kind === "leaf") {
        if (!isFeatureOn(features, node.featureId)) return null;
        return {
          key: node.path,
          icon: node.icon ? <PlatformIcon name={node.icon} /> : undefined,
          label: <Link to={node.path}>{node.label}</Link>,
        };
      }
      if (!isFeatureOn(features, node.featureId)) return null;
      const children = node.children
        .map(mapNode)
        .filter((x): x is NonNullable<typeof x> => x != null);
      if (!children.length) return null;
      return {
        key: node.key,
        icon: node.icon ? <PlatformIcon name={node.icon} /> : undefined,
        label: node.label,
        children,
      };
    };
    return GUIDE_NAV.map(mapNode).filter(
      (x): x is NonNullable<typeof x> => x != null,
    );
  }, [features]);

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

  const adminMenuItems = buildAdminMenuItems();

  const menuItems = [
    ...(platformItems.length
      ? [{ type: "group" as const, label: "平台", children: platformItems }]
      : []),
    ...(guideItems.length
      ? [{ type: "group" as const, label: "攻略", children: guideItems }]
      : []),
    { type: "group" as const, label: "我的", children: mineItems },
    ...(isAdmin
      ? [
          {
            type: "group" as const,
            label: "管理",
            children: adminMenuItems,
          },
        ]
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

  const isTarkovGuide = location.pathname.startsWith("/guides/tarkov");

  return (
    <Layout style={{ height: "100vh", overflow: "hidden" }}>
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
            openKeys={openKeys}
            onOpenChange={setOpenKeys}
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
                <AppVersion
                  light
                  hasUpdate={hasAppUpdate}
                  latestVersion={appUpdateQuery.data?.latest_version}
                />
              </div>
            </div>
          </div>
        </div>
      </Sider>
      <Layout
        style={{
          height: "100vh",
          overflow: "hidden",
          display: "flex",
          flexDirection: "column",
        }}
      >
        {isTarkovGuide ? null : (
          <Header
            style={{
              background: token.colorBgContainer,
              padding: "0 24px",
              height: 56,
              lineHeight: "56px",
              flexShrink: 0,
              borderBottom: `1px solid ${token.colorBorderSecondary}`,
            }}
          />
        )}
        <Content
          className={isTarkovGuide ? "app-main-tarkov" : "app-main-scroll"}
          style={
            isTarkovGuide
              ? { flex: 1, minHeight: 0, margin: 0, overflow: "hidden" }
              : { flex: 1, minHeight: 0, margin: 24, overflow: "auto" }
          }
        >
          {isTarkovGuide ? (
            <Outlet />
          ) : (
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
          )}
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
