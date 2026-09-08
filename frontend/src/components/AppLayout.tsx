import {
  AuditOutlined,
  CalendarOutlined,
  CoffeeOutlined,
  CloudDownloadOutlined,
  FileTextOutlined,
  KeyOutlined,
  LockOutlined,
  LoginOutlined,
  LogoutOutlined,
  MailOutlined,
  MenuFoldOutlined,
  MenuOutlined,
  MenuUnfoldOutlined,
  ScheduleOutlined,
  SettingOutlined,
  TeamOutlined,
  UserOutlined,
} from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import {
  Avatar,
  Button,
  Drawer,
  Grid,
  Layout,
  Menu,
  Tag,
  Tooltip,
  Typography,
  theme,
} from "antd";
import type { MenuProps } from "antd";
import { Suspense, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Link, Outlet, useLocation, useNavigate } from "react-router-dom";
import { fetchAppUpdateStatus } from "@/api/appUpdateApi";
import { fetchMe, fetchMyProfile, fetchPlatformFeaturesEffective, logoutRequest } from "@/api/client";
import { AppVersion } from "@/components/AppVersion";
import { BrandLogo } from "@/components/BrandLogo";
import { IcpBeianFooter } from "@/components/IcpBeianLink";
import { RouteFallback } from "@/components/RouteFallback";
import { PageMotion } from "@/components/PageMotion";
import { RouteErrorBoundary } from "@/components/RouteErrorBoundary";
import { CompleteProfileModal } from "@/components/CompleteProfileModal";
import { PlatformIcon } from "@/components/PlatformIcon";
import { adminContentShell } from "@/lib/adminContentShell";
import { shouldPromptCompleteProfile } from "@/lib/completeProfile";
import { isAdminUser } from "@/lib/isAdminUser";
import { GUIDE_LEAF_PATHS, GUIDE_NAV, type GuideNavNode } from "@/lib/guideNav";
import {
  PLATFORM_NAV,
  firstEnabledPlatformPath,
  isFeatureOn,
} from "@/lib/platformFeatures";
import {
  loadAppSiderCollapsed,
  saveAppSiderCollapsed,
} from "@/lib/appSiderPrefs";
import { focusWithoutVisibleRing } from "@/lib/focusRouteTarget";
import { LOCAL_QUERY_STALE_MS } from "@/lib/queryCache";
import { TAVERN_ADMIN_PATH, TAVERN_FEATURE_ID, TAVERN_PATH } from "@/lib/tavernNav";
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
  "/mihoyo",
  "/exilium",
  "/daily",
  "/profile",
  TAVERN_PATH,
  TAVERN_ADMIN_PATH,
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
  ];
}

export function AppLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const setUser = useAuthStore((s) => s.setUser);
  const logout = useAuthStore((s) => s.logout);
  const loggedIn = Boolean(user);
  const { token } = theme.useToken();
  const [completeOpen, setCompleteOpen] = useState(false);
  const [openKeys, setOpenKeys] = useState<string[]>([]);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [siderCollapsed, setSiderCollapsed] = useState(loadAppSiderCollapsed);
  const screens = Grid.useBreakpoint();
  const isMobile = screens.md === false;
  const isTarkovGuide = location.pathname.startsWith("/guides/tarkov");
  const contentShell = adminContentShell(location.pathname);
  const mainRef = useRef<HTMLElement>(null);

  const featuresQuery = useQuery({
    queryKey: ["platform-features-effective"],
    queryFn: fetchPlatformFeaturesEffective,
    staleTime: LOCAL_QUERY_STALE_MS,
    enabled: loggedIn,
  });

  const meQuery = useQuery({
    queryKey: ["auth-me"],
    queryFn: fetchMe,
    staleTime: LOCAL_QUERY_STALE_MS,
    enabled: loggedIn,
  });

  const profileQuery = useQuery({
    queryKey: ["profile-me"],
    queryFn: fetchMyProfile,
    staleTime: LOCAL_QUERY_STALE_MS,
    enabled: loggedIn,
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
    if (!loggedIn || !meQuery.isSuccess) {
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
    loggedIn,
    user?.email,
  ]);

  useLayoutEffect(() => {
    mainRef.current?.scrollTo(0, 0);
    if (!isTarkovGuide) {
      focusWithoutVisibleRing(mainRef.current);
    }
  }, [location.pathname, isTarkovGuide]);

  useEffect(() => {
    setDrawerOpen(false);
  }, [location.pathname]);

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
    if (location.pathname.startsWith(TAVERN_ADMIN_PATH)) {
      return TAVERN_ADMIN_PATH;
    }
    if (location.pathname === "/" || location.pathname.startsWith(TAVERN_PATH)) {
      return TAVERN_PATH;
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
    if (location.pathname.startsWith("/mihoyo")) return "/mihoyo";
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

  const isAdmin = loggedIn && isAdminUser(user);
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

  const communityItems = [
    ...(!loggedIn || isFeatureOn(features, TAVERN_FEATURE_ID)
      ? [
          {
            key: TAVERN_PATH,
            icon: <CoffeeOutlined />,
            label: <Link to={TAVERN_PATH}>战鸽酒馆</Link>,
          },
        ]
      : []),
    ...(loggedIn && isAdmin && isFeatureOn(features, TAVERN_FEATURE_ID)
      ? [
          {
            key: TAVERN_ADMIN_PATH,
            icon: <AuditOutlined />,
            label: <Link to={TAVERN_ADMIN_PATH}>酒馆管理</Link>,
          },
        ]
      : []),
  ];

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

  const adminMenuItems = buildAdminMenuItems() || [];

  const menuItems = [
    ...(communityItems.length
      ? [{ type: "group" as const, label: "社区", children: communityItems }]
      : []),
    ...(loggedIn
      ? [{ type: "group" as const, label: "我的", children: mineItems }]
      : []),
    ...(platformItems.length
      ? [{ type: "group" as const, label: "平台", children: platformItems }]
      : []),
    ...(guideItems.length
      ? [{ type: "group" as const, label: "游戏", children: guideItems }]
      : []),
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
    if (!loggedIn || featuresQuery.isLoading) return;
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
    loggedIn,
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

  const homeHref = TAVERN_PATH;
  const pageGutter = contentShell === "flush" ? 0 : isMobile ? 12 : 24;

  const onLogout = () => {
    void logoutRequest().catch(() => undefined);
    logout();
    navigate("/login");
  };

  const toggleSider = (collapsed: boolean) => {
    setSiderCollapsed(collapsed);
    saveAppSiderCollapsed(collapsed);
  };

  const versionEl = (
    <AppVersion
      light
      inline
      hasUpdate={hasAppUpdate}
      latestVersion={appUpdateQuery.data?.latest_version}
    />
  );

  const siderInner = (
    <div
      style={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
      }}
    >
      <div className="app-sider-brand">
        <div className="app-sider-brand-top">
          <Link to={homeHref} className="app-sider-brand-link">
            <BrandLogo size={32} color="#e8b86d" />
            <Typography.Text
              strong
              style={{ color: "#e8b86d", fontSize: 16, letterSpacing: 1 }}
            >
              战鸽数据
            </Typography.Text>
          </Link>
          {versionEl}
          {isMobile ? null : (
            <Tooltip title="收起侧栏">
              <Button
                type="text"
                size="small"
                className="app-sider-brand-toggle"
                icon={<MenuFoldOutlined />}
                aria-label="收起侧栏"
                aria-expanded
                onClick={() => toggleSider(true)}
              />
            </Tooltip>
          )}
        </div>
      </div>
      <nav
        aria-label="站点"
        style={{
          flex: 1,
          minHeight: 0,
          display: "flex",
          flexDirection: "column",
        }}
      >
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
      </nav>
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
            {loggedIn ? (
              <>
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
                    size="small"
                    className="sider-logout-btn"
                    icon={<LogoutOutlined />}
                    aria-label="退出登录"
                    onClick={onLogout}
                  />
                </Tooltip>
              </>
            ) : (
              <Link
                to="/login"
                state={{ from: location }}
                style={{ display: "block", width: "100%" }}
              >
                <Button
                  type="primary"
                  block
                  size="small"
                  icon={<LoginOutlined />}
                >
                  登录
                </Button>
              </Link>
            )}
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <Layout style={{ height: "100vh", overflow: "hidden" }}>
      {isTarkovGuide ? null : (
        <a className="skip-to-main" href="#app-main">
          跳到正文
        </a>
      )}
      {isMobile ? (
        <Drawer
          placement="left"
          open={drawerOpen}
          onClose={() => setDrawerOpen(false)}
          width={220}
          closable={false}
          styles={{
            body: { padding: 0, background: "#1a2332", height: "100%" },
          }}
        >
          {siderInner}
        </Drawer>
      ) : siderCollapsed ? null : (
        <Sider
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
          {siderInner}
        </Sider>
      )}
      <Layout
        style={{
          height: "100vh",
          overflow: "hidden",
          display: "flex",
          flexDirection: "column",
          background: isTarkovGuide ? "#161710" : undefined,
        }}
      >
        {isMobile ? (
          <Header
            style={{
              background: "#1a2332",
              padding: "0 12px",
              height: 48,
              lineHeight: "48px",
              flexShrink: 0,
              display: "flex",
              alignItems: "center",
              gap: 8,
            }}
          >
            <Button
              type="text"
              size="small"
              icon={<MenuOutlined />}
              aria-label="打开菜单"
              onClick={() => setDrawerOpen(true)}
              style={{ color: "#fff" }}
            />
            <Link to={homeHref} style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <BrandLogo size={22} color="#e8b86d" />
              <Typography.Text strong style={{ color: "#e8b86d" }}>
                战鸽数据
              </Typography.Text>
            </Link>
            <AppVersion
              light
              inline
              hasUpdate={hasAppUpdate}
              latestVersion={appUpdateQuery.data?.latest_version}
            />
          </Header>
        ) : null}
        <Content
          ref={mainRef}
          id={isTarkovGuide ? undefined : "app-main"}
          role={isTarkovGuide ? undefined : "main"}
          tabIndex={isTarkovGuide ? undefined : -1}
          className={[
            isTarkovGuide ? "app-main-tarkov" : "app-main-scroll",
            !isMobile && siderCollapsed ? "app-main--sider-collapsed" : "",
          ]
            .filter(Boolean)
            .join(" ")}
          style={
            isTarkovGuide
              ? { flex: 1, minHeight: 0, margin: 0, overflow: "hidden" }
              : {
                  flex: 1,
                  minWidth: 0,
                  minHeight: 0,
                  margin: pageGutter,
                  overflowX: "hidden",
                  overflowY: "scroll",
                  scrollbarGutter: "stable",
                  ...(contentShell === "flush"
                    ? { background: token.colorBgLayout }
                    : {}),
                }
          }
        >
          {isTarkovGuide ? (
            <Suspense fallback={<RouteFallback />}>
              <RouteErrorBoundary resetKey="/guides/tarkov">
                <Outlet />
              </RouteErrorBoundary>
            </Suspense>
          ) : (
            <div
              className={
                contentShell
                  ? `app-page-shell app-page-shell--${contentShell}`
                  : undefined
              }
              style={
                contentShell === "flush"
                  ? {
                      background: "transparent",
                      padding: 0,
                      boxShadow: "none",
                      flex: "1 0 auto",
                      display: "flex",
                      flexDirection: "column",
                      width: "100%",
                    }
                  : contentShell
                    ? { background: token.colorBgContainer }
                    : {
                        background: token.colorBgContainer,
                        padding: 24,
                        borderRadius: 8,
                        minHeight: 360,
                      }
              }
            >
              <Suspense fallback={<RouteFallback />}>
                <RouteErrorBoundary resetKey={location.pathname}>
                  <PageMotion motionKey={location.pathname}>
                    <Outlet />
                  </PageMotion>
                </RouteErrorBoundary>
              </Suspense>
            </div>
          )}
          {isTarkovGuide ? null : <IcpBeianFooter />}
        </Content>
      </Layout>
      {isMobile || !siderCollapsed ? null : (
        <div className="app-sider-edge-slot">
          <Tooltip title="展开侧栏" placement="right">
            <Button
              type="text"
              size="small"
              className="app-sider-edge-toggle"
              icon={<MenuUnfoldOutlined />}
              aria-label="展开侧栏"
              aria-expanded={false}
              onClick={() => toggleSider(false)}
            />
          </Tooltip>
        </div>
      )}
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
