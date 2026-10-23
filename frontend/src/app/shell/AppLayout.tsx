import {
  AuditOutlined,
  CalendarOutlined,
  CloudServerOutlined,
  CoffeeOutlined,
  LoginOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuOutlined,
  MenuUnfoldOutlined,
  ScheduleOutlined,
  SettingOutlined,
  SwapOutlined,
  TeamOutlined,
  UserOutlined,
} from "@ant-design/icons";
import { useQuery } from "@tanstack/react-query";
import {
  Avatar,
  Badge,
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
import { fetchAppUpdateStatus } from "@/features/admin/api/appUpdateApi";
import { fetchMe, logoutRequest } from "@/features/auth/api/authApi";
import { fetchMyProfile } from "@/features/profile/api/usersApi";
import { fetchPlatformFeaturesEffective } from "@/features/platforms/shared/api/platformFeaturesApi";
import { AppReloadBanner } from "@/app/shell/AppReloadBanner";
import { AppVersion } from "@/app/shell/AppVersion";
import { BrandLogo } from "@/shared/ui/BrandLogo";
import { IcpBeianFooter } from "@/features/site/components/IcpBeianLink";
import { RouteFallback } from "@/app/router/RouteFallback";
import { PageMotion } from "@/shared/ui/PageMotion";
import { RouteErrorBoundary } from "@/app/router/RouteErrorBoundary";
import { CompleteProfileModal } from "@/features/profile/components/CompleteProfileModal";
import { PlatformIcon } from "@/features/platforms/shared/components/PlatformIcon";
import { adminContentShell } from "@/features/admin/model/adminContentShell";
import { isAssistantEmbed } from "@/shared/lib/assistantShell";
import { BRAND_NAVY } from "@/shared/styles/tokens";
import {
  ADMIN_HUBS,
  ADMIN_LEAF_PATHS,
  ADMIN_USERS_PATH,
  adminMenuSelectedKey,
  adminOpsLandingPath,
  adminPageMotionKey,
} from "@/features/admin/model/adminHub";
import { shouldPromptCompleteProfile } from "@/features/profile/model/completeProfile";
import { isAdminUser } from "@/features/auth/model/isAdminUser";
import { GUIDE_LEAF_PATHS, GUIDE_NAV, type GuideNavNode } from "@/features/guides/shared/model/guideNav";
import {
  PLATFORM_NAV,
  firstEnabledPlatformPath,
  isFeatureOn,
  platformFeatureMenuKey,
} from "@/features/platforms/shared/model/platformFeatures";
import {
  loadAppSiderCollapsed,
  saveAppSiderCollapsed,
} from "@/app/lib/appSiderPrefs";
import { focusWithoutVisibleRing } from "@/shared/lib/focusRouteTarget";
import { LOCAL_QUERY_STALE_MS } from "@/shared/lib/queryCache";
import { TAVERN_ADMIN_PATH, TAVERN_FEATURE_ID, TAVERN_PATH } from "@/features/articles/model/tavernNav";
import { useAuthStore } from "@/features/auth/model/authStore";

const { Header, Sider, Content } = Layout;

const GUIDE_LEAF_KEYS = GUIDE_LEAF_PATHS;

const leafKeys = [
  ...ADMIN_LEAF_PATHS,
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

function buildAdminMenuItems(hasAppUpdate: boolean): MenuProps["items"] {
  const opsPath = adminOpsLandingPath(hasAppUpdate);
  const siteHub = ADMIN_HUBS.find((h) => h.id === "site");
  const opsHub = ADMIN_HUBS.find((h) => h.id === "ops");
  const jobsHub = ADMIN_HUBS.find((h) => h.id === "jobs");
  const usersHub = ADMIN_HUBS.find((h) => h.id === "users");
  return [
    {
      key: "admin-site",
      icon: <SettingOutlined />,
      label: <Link to="/settings/auth">{siteHub?.label}</Link>,
    },
    {
      key: "admin-ops",
      icon: <CloudServerOutlined />,
      label: (
        <Link to={opsPath}>
          <Badge dot={hasAppUpdate} offset={[4, 0]}>
            {opsHub?.label}
          </Badge>
        </Link>
      ),
    },
    {
      key: "admin-jobs",
      icon: <ScheduleOutlined />,
      label: <Link to="/settings/task-config">{jobsHub?.label}</Link>,
    },
    {
      key: usersHub?.menuKey ?? ADMIN_USERS_PATH,
      icon: <TeamOutlined />,
      label: <Link to={ADMIN_USERS_PATH}>{usersHub?.label}</Link>,
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
  const assistantEmbed = isAssistantEmbed();
  const isTarkovGuide = location.pathname.startsWith("/guides/tarkov");
  const isRor2Guide = location.pathname.startsWith("/guides/ror2");
  const isFullBleedGuide = isTarkovGuide || isRor2Guide;
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
    /* 登出后迟到的 /auth/me 不得把上一位用户写回 store */
    if (!meQuery.data || !useAuthStore.getState().user) return;
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
      navigate(
        { pathname: location.pathname, search: location.search, hash: location.hash },
        { replace: true, state: {} },
      );
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
    location.search,
    location.hash,
    location.state,
    meQuery.data,
    meQuery.isSuccess,
    navigate,
    loggedIn,
    user?.email,
  ]);

  useLayoutEffect(() => {
    mainRef.current?.scrollTo(0, 0);
    if (!isFullBleedGuide) {
      focusWithoutVisibleRing(mainRef.current);
    }
  }, [location.pathname, isFullBleedGuide]);

  useEffect(() => {
    setDrawerOpen(false);
  }, [location.pathname, location.search]);

  const selected = useMemo(() => {
    if (location.pathname === "/app") return "/app";
    if (/^\/members\/\d+\/profile/.test(location.pathname)) {
      return ADMIN_USERS_PATH;
    }
    if (location.pathname.startsWith("/settings/")) {
      const hit = adminMenuSelectedKey(location.pathname);
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
    const platform = PLATFORM_NAV.find(
      (item) =>
        location.pathname === item.path ||
        location.pathname.startsWith(item.path + "/"),
    );
    if (platform) {
      const requestedTab = new URLSearchParams(location.search).get("tab");
      const child = platform.children?.find((item) => item.key === requestedTab);
      return child
        ? platformFeatureMenuKey(platform.path, child.key)
        : platform.path;
    }
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
  }, [location.pathname, location.search]);

  const selectedPlatformParent = PLATFORM_NAV.find((item) =>
    item.children?.some(
      (child) => platformFeatureMenuKey(item.path, child.key) === selected,
    ),
  )?.path;

  useEffect(() => {
    if (!selectedPlatformParent) return;
    setOpenKeys((current) =>
      current.includes(selectedPlatformParent)
        ? current
        : [...current, selectedPlatformParent],
    );
  }, [selectedPlatformParent]);

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
  ).map((item) => {
    const children = (item.children || [])
      .filter((child) => isFeatureOn(features, child.featureId))
      .map((child) => ({
        key: platformFeatureMenuKey(item.path, child.key),
        icon:
          child.icon === "exchange" ? (
            <SwapOutlined />
          ) : child.icon ? (
            <PlatformIcon name={child.icon} />
          ) : undefined,
        label: (
          <Link to={platformFeatureMenuKey(item.path, child.key)}>
            {child.label}
          </Link>
        ),
      }));

    return {
      key: item.path,
      icon: <PlatformIcon name={item.icon} />,
      label: <Link to={item.path}>{item.label}</Link>,
      ...(children.length ? { children } : {}),
    };
  });

  const guideItems = useMemo(() => {
    const mapNode = (node: GuideNavNode): NonNullable<MenuProps["items"]>[number] | null => {
      if (node.kind === "leaf") {
        if (loggedIn) {
          if (!isFeatureOn(features, node.featureId)) return null;
        } else if (!node.allowGuest) {
          return null;
        }
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
  }, [features, loggedIn]);

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

  const adminMenuItems = buildAdminMenuItems(hasAppUpdate) || [];

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
          background: BRAND_NAVY,
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
    <Layout
      style={{
        height: "100vh",
        overflow: "hidden",
        background: isTarkovGuide ? "#161710" : isRor2Guide ? "#121216" : undefined,
      }}
    >
      {isFullBleedGuide ? null : (
        <a className="skip-to-main" href="#app-main">
          跳到正文
        </a>
      )}
      {assistantEmbed ? null : isMobile ? (
        <Drawer
          placement="left"
          open={drawerOpen}
          onClose={() => setDrawerOpen(false)}
          width={220}
          closable={false}
          styles={{
            body: { padding: 0, background: BRAND_NAVY, height: "100%" },
          }}
        >
          {siderInner}
        </Drawer>
      ) : siderCollapsed ? null : (
        <Sider
          width={220}
          style={{
            background: BRAND_NAVY,
            height: "100%",
            alignSelf: "stretch",
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
          background: isTarkovGuide ? "#161710" : isRor2Guide ? "#121216" : undefined,
        }}
      >
        {isMobile && !assistantEmbed ? (
          <Header
            style={{
              background: BRAND_NAVY,
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
        <AppReloadBanner />
        <Content
          ref={mainRef}
          id={isFullBleedGuide ? undefined : "app-main"}
          role={isFullBleedGuide ? undefined : "main"}
          tabIndex={isFullBleedGuide ? undefined : -1}
          className={[
            isFullBleedGuide ? "app-main-canvas" : "app-main-scroll",
            !assistantEmbed && !isMobile && siderCollapsed
              ? "app-main--sider-collapsed"
              : "",
          ]
            .filter(Boolean)
            .join(" ")}
          style={
            isFullBleedGuide
              ? { flex: 1, minHeight: 0, margin: 0, overflow: "hidden" }
              : {
                  flex: 1,
                  minWidth: 0,
                  minHeight: 0,
                  margin: pageGutter,
                  overflowX: "hidden",
                  overflowY: "auto",
                  ...(contentShell === "flush"
                    ? { background: token.colorBgLayout }
                    : {}),
                }
          }
        >
          {isFullBleedGuide ? (
            <Suspense fallback={<RouteFallback />}>
              <RouteErrorBoundary resetKey={isRor2Guide ? "/guides/ror2" : "/guides/tarkov"}>
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
                  <PageMotion motionKey={adminPageMotionKey(location.pathname)}>
                    <Outlet />
                  </PageMotion>
                </RouteErrorBoundary>
              </Suspense>
            </div>
          )}
          {isFullBleedGuide ? null : <IcpBeianFooter />}
        </Content>
      </Layout>
      {assistantEmbed || isMobile || !siderCollapsed ? null : (
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
