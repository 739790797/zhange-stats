import { Suspense, useEffect, useMemo, useRef, type ReactNode } from "react";
import { App as AntdApp, ConfigProvider } from "antd";
import {
  BrowserRouter,
  Navigate,
  Outlet,
  Route,
  Routes,
  useLocation,
  useNavigate,
  useParams,
} from "react-router-dom";
import { client } from "@/shared/api/http";
import { isAdminUser } from "@/features/auth/model/isAdminUser";
import { AdminRoute, PrivateRoute } from "@/app/router/PrivateRoute";
import { HomeRedirect } from "@/app/router/HomeRedirect";
import { NotFoundPage } from "@/app/router/NotFoundPage";
import { PlatformRoute } from "@/app/router/PlatformRoute";
import { RouteErrorBoundary } from "@/app/router/RouteErrorBoundary";
import { RouteFallback } from "@/app/router/RouteFallback";
import { PanelFallback } from "@/shared/ui/PanelFallback";
import { PageMotion } from "@/shared/ui/PageMotion";
import { SetupGate } from "@/features/auth/components/SetupGate";
import { AuthGuestContentBoundaryContext } from "@/features/auth/components/AuthGuestContentBoundary";
import { antdLocale } from "@/shared/locales/zhCN";
import { lazyWithReload } from "@/app/lib/chunkReload";
import { usePrefersReducedMotion } from "@/shared/hooks/prefersReducedMotion";
import { TarkovGameModeProvider } from "@/features/guides/tarkov/providers/tarkovGameModeProvider";
import { TAVERN_ADMIN_PATH, TAVERN_WRITE_PATH, tavernEditPath } from "@/features/articles/model/tavernNav";
import { antdThemeWithMotion } from "@/app/theme/antdApp";
import { useAuthStore } from "@/features/auth/model/authStore";
import {
  isUpstreamRepoNotSyncedError,
  upstreamRepoForResourcePath,
  UPSTREAM_REPO_NOT_SYNCED_EVENT,
} from "@/app/http/upstreamRepoSyncPrompt";

const AppLayout = lazyWithReload(() =>
  import("@/app/shell/AppLayout").then((m) => ({ default: m.AppLayout })),
);
const AdminHubLayout = lazyWithReload(() =>
  import("@/features/admin/components/AdminHubLayout").then((m) => ({
    default: m.AdminHubLayout,
  })),
);
const SetupPage = lazyWithReload(() => import("@/features/auth/pages/SetupPage"));
const LoginPage = lazyWithReload(() => import("@/features/auth/pages/LoginPage"));
const AppHomePage = lazyWithReload(() => import("@/features/home/pages/AppHomePage"));
const LegalTermsPage = lazyWithReload(() => import("@/features/legal/pages/LegalTermsPage"));
const LegalPrivacyPage = lazyWithReload(() => import("@/features/legal/pages/LegalPrivacyPage"));
const RegisterPage = lazyWithReload(() => import("@/features/auth/pages/RegisterPage"));
const ForgotPasswordPage = lazyWithReload(() => import("@/features/auth/pages/ForgotPasswordPage"));
const VerifyEmailPage = lazyWithReload(() => import("@/features/auth/pages/VerifyEmailPage"));
const SteamCalendarPage = lazyWithReload(() => import("@/features/platforms/steam/pages/SteamCalendarPage"));
const SklandPage = lazyWithReload(() => import("@/features/platforms/skland/pages/SklandPage"));
const TaygedoPage = lazyWithReload(() => import("@/features/platforms/taygedo/pages/TaygedoPage"));
const ExiliumPage = lazyWithReload(() => import("@/features/platforms/exilium/pages/ExiliumPage"));
const KujiequPage = lazyWithReload(() => import("@/features/platforms/kujiequ/pages/KujiequPage"));
const MihoyoPage = lazyWithReload(() => import("@/features/platforms/mihoyo/pages/MihoyoPage"));
const MyDailyPage = lazyWithReload(() => import("@/features/daily/pages/MyDailyPage"));
const ProfileSettingsPage = lazyWithReload(() => import("@/features/profile/pages/ProfileSettingsPage"));
const UserManagementPage = lazyWithReload(() => import("@/features/admin/pages/UserManagementPage"));
const IntegrationsSettingsPage = lazyWithReload(
  () => import("@/features/admin/pages/IntegrationsSettingsPage"),
);
const AuthSettingsPage = lazyWithReload(() => import("@/features/admin/pages/AuthSettingsPage"));
const EmailSettingsPage = lazyWithReload(() => import("@/features/admin/pages/EmailSettingsPage"));
const FileManagerPage = lazyWithReload(() => import("@/features/admin/pages/FileManagerPage"));
const TaskConfigPage = lazyWithReload(() => import("@/features/admin/pages/TaskConfigPage"));
const ScheduledJobsPage = lazyWithReload(() => import("@/features/admin/pages/ScheduledJobsPage"));
const PlatformLogsPage = lazyWithReload(() => import("@/features/admin/pages/PlatformLogsPage"));
const RumPage = lazyWithReload(() => import("@/features/admin/pages/RumPage"));
const RuntimeEnvPage = lazyWithReload(() => import("@/features/admin/pages/RuntimeEnvPage"));
const SystemUpdatePage = lazyWithReload(() => import("@/features/admin/pages/SystemUpdatePage"));
const TarkovGuidesRoute = lazyWithReload(() => import("@/app/router/TarkovGuidesRoute"));
const Ror2GuidesRoute = lazyWithReload(() => import("@/app/router/Ror2GuidesRoute"));
const Ror2HomePage = lazyWithReload(() => import("@/features/guides/ror2/pages/Ror2HomePage"));
const Ror2ItemsPage = lazyWithReload(() => import("@/features/guides/ror2/pages/Ror2ItemsPage"));
const Ror2ItemDetailPage = lazyWithReload(() => import("@/features/guides/ror2/pages/Ror2ItemDetailPage"));
const Ror2SurvivorsPage = lazyWithReload(() => import("@/features/guides/ror2/pages/Ror2SurvivorsPage"));
const Ror2SurvivorPage = lazyWithReload(() => import("@/features/guides/ror2/pages/Ror2SurvivorPage"));
const Ror2DirectoryPage = lazyWithReload(() => import("@/features/guides/ror2/pages/Ror2DirectoryPage"));
const TarkovHomePage = lazyWithReload(() => import("@/features/guides/tarkov/pages/TarkovHomePage"));
const TarkovItemsHubPage = lazyWithReload(
  () => import("@/features/guides/tarkov/pages/TarkovItemsHubPage"),
);
const TarkovItemTypePage = lazyWithReload(
  () => import("@/features/guides/tarkov/pages/TarkovItemTypePage"),
);
const TarkovItemDetailPage = lazyWithReload(
  () => import("@/features/guides/tarkov/pages/TarkovItemDetailPage"),
);
const TarkovTasksPage = lazyWithReload(() => import("@/features/guides/tarkov/pages/TarkovTasksPage"));
const TarkovRaidPrepPage = lazyWithReload(
  () => import("@/features/guides/tarkov/pages/TarkovRaidPrepPage"),
);
const TarkovRaidRoomPage = lazyWithReload(
  () => import("@/features/guides/tarkov/pages/TarkovRaidRoomPage"),
);
const TarkovRaidPulseDemoPage = lazyWithReload(
  () => import("@/features/guides/tarkov/pages/TarkovRaidPulseDemoPage"),
);
const TarkovTaskDetailPage = lazyWithReload(
  () => import("@/features/guides/tarkov/pages/TarkovTaskDetailPage"),
);
const TarkovTradersPage = lazyWithReload(() => import("@/features/guides/tarkov/pages/TarkovTradersPage"));
const TarkovTraderPage = lazyWithReload(() => import("@/features/guides/tarkov/pages/TarkovTraderPage"));
const TarkovBossesPage = lazyWithReload(() => import("@/features/guides/tarkov/pages/TarkovBossesPage"));
const TarkovBossPage = lazyWithReload(() => import("@/features/guides/tarkov/pages/TarkovBossPage"));
const TarkovMapsPage = lazyWithReload(() => import("@/features/guides/tarkov/pages/TarkovMapsPage"));
const TarkovMapDetailPage = lazyWithReload(
  () => import("@/features/guides/tarkov/pages/TarkovMapDetailPage"),
);
const TarkovHideoutPage = lazyWithReload(() => import("@/features/guides/tarkov/pages/TarkovHideoutPage"));
const TarkovHideoutDetailPage = lazyWithReload(
  () => import("@/features/guides/tarkov/pages/TarkovHideoutDetailPage"),
);
const TarkovWorkbenchPage = lazyWithReload(
  () => import("@/features/guides/tarkov/pages/TarkovWorkbenchPage"),
);
const TarkovMePage = lazyWithReload(() => import("@/features/guides/tarkov/pages/TarkovMePage"));
const TarkovKeyPacksPage = lazyWithReload(
  () => import("@/features/guides/tarkov/pages/TarkovKeyPacksPage"),
);
const TarkovGameLogsPage = lazyWithReload(
  () => import("@/features/guides/tarkov/pages/TarkovGameLogsPage"),
);
const TarkovCollectionPage = lazyWithReload(
  () => import("@/features/guides/tarkov/pages/TarkovCollectionPage"),
);
const TarkovProgressionPage = lazyWithReload(
  () => import("@/features/guides/tarkov/pages/TarkovProgressionPage"),
);
// const MinecraftPage = lazyWithReload(() => import("@/features/guides/minecraft/pages/MinecraftPage"));
const TavernListPage = lazyWithReload(() => import("@/features/articles/pages/TavernListPage"));
const TavernArticlePage = lazyWithReload(() => import("@/features/articles/pages/TavernArticlePage"));
const TavernAdminPage = lazyWithReload(() => import("@/features/articles/pages/TavernAdminPage"));
const TavernEditPage = lazyWithReload(() => import("@/features/articles/pages/TavernEditPage"));

function AdminPage({ children }: { children: ReactNode }) {
  return <AdminRoute>{children}</AdminRoute>;
}

function RedirectTavernManageEdit() {
  const { articleId } = useParams();
  if (!articleId || articleId === "new") {
    return <Navigate to={TAVERN_WRITE_PATH} replace />;
  }
  return <Navigate to={tavernEditPath(Number(articleId))} replace />;
}

const antdLocaleWithActions = {
  ...antdLocale,
  Modal: {
    ...antdLocale.Modal,
    okText: "确定",
    cancelText: "取消",
    justOkText: antdLocale.Modal?.justOkText ?? "知道了",
  },
  Popconfirm: {
    ...antdLocale.Popconfirm,
    okText: "确定",
    cancelText: "取消",
  },
};

function AuthGuestPageBoundary({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();
  const wrapContent = useMemo(
    () => (content: ReactNode) => (
      <RouteErrorBoundary resetKey={pathname}>{content}</RouteErrorBoundary>
    ),
    [pathname],
  );
  return (
    <AuthGuestContentBoundaryContext.Provider value={wrapContent}>
      {children}
    </AuthGuestContentBoundaryContext.Provider>
  );
}

function AdminHubRouteLayout() {
  const location = useLocation();
  return (
    <AdminHubLayout>
      <Suspense fallback={<PanelFallback />}>
        <RouteErrorBoundary resetKey={location.pathname}>
          <PageMotion motionKey={location.pathname}>
            <Outlet />
          </PageMotion>
        </RouteErrorBoundary>
      </Suspense>
    </AdminHubLayout>
  );
}

/** 布局之外（登录页、安装向导、布局本身）出错时的兜底；布局里的页面另有一层。 */
function SetupGateWithBoundary({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();
  return (
    <RouteErrorBoundary resetKey={pathname}>
      <SetupGate>{children}</SetupGate>
    </RouteErrorBoundary>
  );
}

function UpstreamRepoSyncPrompt() {
  const { modal } = AntdApp.useApp();
  const navigate = useNavigate();
  const location = useLocation();
  const user = useAuthStore((state) => state.user);
  const canSync = isAdminUser(user);
  const promptedPath = useRef<string | null>(null);
  const resourceProbeCooldown = useRef(new Map<string, number>());

  useEffect(() => {
    promptedPath.current = null;
    resourceProbeCooldown.current.clear();
  }, [location.pathname]);

  useEffect(() => {
    const showPrompt = () => {
      if (promptedPath.current === location.pathname) return;
      promptedPath.current = location.pathname;
      modal.confirm({
        title: "外部仓库尚未同步",
        content: canSync
          ? "当前内容所需的外部数据仓还未同步。前往「任务配置」页，手动运行「外部仓库更新」后再试。"
          : "当前内容所需的外部数据仓还未同步，请联系管理员前往「任务配置」页运行「外部仓库更新」。",
        okText: canSync ? "前往同步页面" : "知道了",
        cancelText: canSync ? "稍后" : undefined,
        cancelButtonProps: canSync ? undefined : { style: { display: "none" } },
        onOk: canSync ? () => navigate("/settings/task-config") : undefined,
      });
    };

    const probeFailedRepoImage = (event: Event) => {
      const target = event.target;
      if (!(target instanceof HTMLImageElement)) return;

      let resourceUrl: URL;
      try {
        resourceUrl = new URL(target.currentSrc || target.src, window.location.href);
      } catch {
        return;
      }
      if (resourceUrl.origin !== window.location.origin) return;
      const repoId = upstreamRepoForResourcePath(resourceUrl.pathname);
      if (!repoId) return;

      const now = Date.now();
      if ((resourceProbeCooldown.current.get(repoId) || 0) > now) return;
      resourceProbeCooldown.current.set(repoId, now + 5000);
      const apiPath = `${resourceUrl.pathname.replace(/^\/api/, "")}${resourceUrl.search}`;
      void client.head(apiPath).catch((error: unknown) => {
        if (!isUpstreamRepoNotSyncedError(error)) {
          resourceProbeCooldown.current.delete(repoId);
        }
      });
    };

    window.addEventListener(UPSTREAM_REPO_NOT_SYNCED_EVENT, showPrompt);
    window.addEventListener("error", probeFailedRepoImage, true);
    return () => {
      window.removeEventListener(UPSTREAM_REPO_NOT_SYNCED_EVENT, showPrompt);
      window.removeEventListener("error", probeFailedRepoImage, true);
    };
  }, [canSync, location.pathname, modal, navigate]);

  return null;
}

function AntdProvider({ children }: { children: ReactNode }) {
  const reducedMotion = usePrefersReducedMotion();
  const theme = useMemo(
    () => antdThemeWithMotion(!reducedMotion),
    [reducedMotion],
  );
  return (
    <ConfigProvider locale={antdLocaleWithActions} theme={theme}>
      <AntdApp>{children}</AntdApp>
    </ConfigProvider>
  );
}

export default function App() {
  return (
    <AntdProvider>
      <BrowserRouter>
        <UpstreamRepoSyncPrompt />
        <SetupGateWithBoundary>
          <Suspense fallback={<RouteFallback />}>
            <Routes>
              <Route path="/setup" element={<AuthGuestPageBoundary><SetupPage /></AuthGuestPageBoundary>} />
              <Route path="/login" element={<AuthGuestPageBoundary><LoginPage /></AuthGuestPageBoundary>} />
              <Route path="/legal/terms" element={<AuthGuestPageBoundary><LegalTermsPage /></AuthGuestPageBoundary>} />
              <Route path="/legal/privacy" element={<AuthGuestPageBoundary><LegalPrivacyPage /></AuthGuestPageBoundary>} />
              <Route path="/register" element={<AuthGuestPageBoundary><RegisterPage /></AuthGuestPageBoundary>} />
              <Route
                path="/forgot-password"
                element={<AuthGuestPageBoundary><ForgotPasswordPage /></AuthGuestPageBoundary>}
              />
              <Route path="/verify-email" element={<AuthGuestPageBoundary><VerifyEmailPage /></AuthGuestPageBoundary>} />
              <Route
                element={
                  <TarkovGameModeProvider>
                    <Suspense fallback={<RouteFallback />}>
                      <AppLayout />
                    </Suspense>
                  </TarkovGameModeProvider>
                }
              >
                <Route path="/" element={<HomeRedirect />} />
                <Route path="/app" element={<AppHomePage />} />
                <Route
                  path="/tavern"
                  element={
                    <PlatformRoute featureId="tavern" allowGuest>
                      <TavernListPage />
                    </PlatformRoute>
                  }
                />
                <Route
                  path="/tavern/write"
                  element={
                    <PrivateRoute>
                      <PlatformRoute featureId="tavern">
                        <TavernEditPage />
                      </PlatformRoute>
                    </PrivateRoute>
                  }
                />
                <Route
                  path="/tavern/write/:articleId"
                  element={
                    <PrivateRoute>
                      <PlatformRoute featureId="tavern">
                        <TavernEditPage />
                      </PlatformRoute>
                    </PrivateRoute>
                  }
                />
                <Route
                  path="/tavern/admin"
                  element={
                    <AdminPage>
                      <PlatformRoute featureId="tavern">
                        <TavernAdminPage />
                      </PlatformRoute>
                    </AdminPage>
                  }
                />
                <Route
                  path="/tavern/manage"
                  element={<Navigate to={TAVERN_ADMIN_PATH} replace />}
                />
                <Route
                  path="/tavern/manage/new"
                  element={<Navigate to={TAVERN_WRITE_PATH} replace />}
                />
                <Route
                  path="/tavern/manage/:articleId"
                  element={<RedirectTavernManageEdit />}
                />
                <Route
                  path="/tavern/:slug"
                  element={
                    <PlatformRoute featureId="tavern" allowGuest>
                      <TavernArticlePage />
                    </PlatformRoute>
                  }
                />
                <Route path="/guides/tarkov" element={<TarkovGuidesRoute />}>
                  <Route index element={<TarkovHomePage />} />
                  <Route path="items" element={<TarkovItemsHubPage />} />
                  <Route
                    path="items/:typeSegment/:itemId"
                    element={<TarkovItemDetailPage />}
                  />
                  <Route
                    path="items/:typeSegment"
                    element={<TarkovItemTypePage />}
                  />
                  <Route path="tasks" element={<TarkovTasksPage />} />
                  <Route
                    path="tasks/:taskId"
                    element={<TarkovTaskDetailPage />}
                  />
                  <Route path="raid-prep" element={<TarkovRaidPrepPage />} />
                  <Route
                    path="raid-prep/pulse-demo"
                    element={
                      <AdminPage>
                        <TarkovRaidPulseDemoPage />
                      </AdminPage>
                    }
                  />
                  <Route
                    path="raid-prep/rooms/:publicId"
                    element={<TarkovRaidRoomPage />}
                  />
                  <Route path="maps" element={<TarkovMapsPage />} />
                  <Route
                    path="maps/:mapSlug"
                    element={<TarkovMapDetailPage />}
                  />
                  <Route path="traders" element={<TarkovTradersPage />} />
                  <Route
                    path="traders/:traderSlug"
                    element={<TarkovTraderPage />}
                  />
                  <Route path="bosses" element={<TarkovBossesPage />} />
                  <Route
                    path="bosses/:bossSlug"
                    element={<TarkovBossPage />}
                  />
                  <Route path="hideout" element={<TarkovHideoutPage />} />
                  <Route
                    path="hideout/:stationSlug"
                    element={<TarkovHideoutDetailPage />}
                  />
                  <Route path="workbench" element={<TarkovWorkbenchPage />} />
                  <Route
                    path="workbench/:gunId"
                    element={<TarkovWorkbenchPage />}
                  />
                  <Route
                    path="barters"
                    element={<Navigate to="/guides/tarkov" replace />}
                  />
                  <Route
                    path="crafts"
                    element={<Navigate to="/guides/tarkov" replace />}
                  />
                  <Route
                    path="loot-tiers"
                    element={<Navigate to="/guides/tarkov" replace />}
                  />
                  <Route
                    path="hideout-cost"
                    element={<Navigate to="/guides/tarkov" replace />}
                  />
                  <Route
                    path="wipe-length"
                    element={<Navigate to="/guides/tarkov" replace />}
                  />
                  <Route
                    path="bitcoin-farm"
                    element={<Navigate to="/guides/tarkov" replace />}
                  />
                  <Route path="me" element={<TarkovMePage />} />
                  <Route
                    path="key-packs"
                    element={<TarkovKeyPacksPage />}
                  />
                  <Route
                    path="game-logs"
                    element={<TarkovGameLogsPage />}
                  />
                  <Route
                    path="collection"
                    element={<TarkovCollectionPage />}
                  />
                  <Route
                    path="progression"
                    element={<TarkovProgressionPage />}
                  />
                </Route>
                <Route path="/guides/ror2" element={<Ror2GuidesRoute />}>
                  <Route index element={<Ror2HomePage />} />
                  <Route path="items" element={<Ror2ItemsPage />} />
                  <Route path="items/:itemKind/:itemId" element={<Ror2ItemDetailPage />} />
                  <Route path="survivors" element={<Ror2SurvivorsPage />} />
                  <Route path="survivors/:name" element={<Ror2SurvivorPage />} />
                  <Route path="monsters" element={<Ror2DirectoryPage section="monsters" />} />
                  <Route path="environments" element={<Ror2DirectoryPage section="environments" />} />
                  <Route path="challenges" element={<Ror2DirectoryPage section="challenges" />} />
                  <Route path="interactables" element={<Ror2DirectoryPage section="interactables" />} />
                  <Route path="drones" element={<Ror2DirectoryPage section="drones" />} />
                  <Route path="artifacts" element={<Ror2DirectoryPage section="artifacts" />} />
                  <Route path="newt-altars" element={<Ror2DirectoryPage section="newt-altars" />} />
                  <Route path="unreleased" element={<Ror2DirectoryPage section="unreleased" />} />
                </Route>
                <Route element={<PrivateRoute />}>
                <Route
                  path="/steam"
                  element={
                    <PlatformRoute featureId="steam">
                      <SteamCalendarPage />
                    </PlatformRoute>
                  }
                />
                <Route path="/friends" element={<HomeRedirect />} />
                <Route
                  path="/skland"
                  element={
                    <PlatformRoute featureId="skland">
                      <SklandPage />
                    </PlatformRoute>
                  }
                />
                <Route
                  path="/taygedo"
                  element={
                    <PlatformRoute featureId="taygedo">
                      <TaygedoPage />
                    </PlatformRoute>
                  }
                />
                <Route
                  path="/exilium"
                  element={
                    <PlatformRoute featureId="exilium">
                      <ExiliumPage />
                    </PlatformRoute>
                  }
                />
                <Route
                  path="/kujiequ"
                  element={
                    <PlatformRoute featureId="kujiequ">
                      <KujiequPage />
                    </PlatformRoute>
                  }
                />
                <Route
                  path="/mihoyo"
                  element={
                    <PlatformRoute featureId="mihoyo">
                      <MihoyoPage />
                    </PlatformRoute>
                  }
                />
                <Route path="/members" element={<HomeRedirect />} />
                <Route path="/daily" element={<MyDailyPage />} />
                {/* Minecraft 页面已停用。
                <Route
                  path="/guides/minecraft"
                  element={
                    <PlatformRoute featureId="guides.minecraft">
                      <MinecraftPage />
                    </PlatformRoute>
                  }
                />
                */}
                <Route path="/profile" element={<ProfileSettingsPage />} />
                <Route
                  path="/members/:id/profile"
                  element={
                    <AdminRoute>
                      <ProfileSettingsPage />
                    </AdminRoute>
                  }
                />
                <Route
                  path="/settings"
                  element={<Navigate to="/settings/users" replace />}
                />
                <Route
                  element={
                    <AdminPage>
                      <AdminHubRouteLayout />
                    </AdminPage>
                  }
                >
                  <Route
                    path="/settings/users"
                    element={<UserManagementPage />}
                  />
                  <Route
                    path="/settings/integrations"
                    element={<IntegrationsSettingsPage />}
                  />
                  <Route path="/settings/auth" element={<AuthSettingsPage />} />
                  <Route
                    path="/settings/email"
                    element={<EmailSettingsPage />}
                  />
                  <Route
                    path="/settings/files"
                    element={<FileManagerPage />}
                  />
                  <Route
                    path="/settings/task-config"
                    element={<TaskConfigPage />}
                  />
                  <Route
                    path="/settings/jobs"
                    element={<ScheduledJobsPage />}
                  />
                  <Route
                    path="/settings/logs"
                    element={<PlatformLogsPage />}
                  />
                  <Route
                    path="/settings/runtime"
                    element={<RuntimeEnvPage />}
                  />
                  <Route path="/settings/rum" element={<RumPage />} />
                  <Route
                    path="/settings/runtime-env"
                    element={<Navigate to="/settings/runtime" replace />}
                  />
                  <Route
                    path="/settings/system"
                    element={<SystemUpdatePage />}
                  />
                </Route>
                </Route>
                <Route path="*" element={<NotFoundPage />} />
              </Route>
            </Routes>
          </Suspense>
        </SetupGateWithBoundary>
      </BrowserRouter>
    </AntdProvider>
  );
}
