import { lazy, Suspense, type ReactNode } from "react";
import { ConfigProvider } from "antd";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AdminRoute, PrivateRoute } from "@/components/PrivateRoute";
import { HomeRedirect } from "@/components/HomeRedirect";
import { NotFoundPage } from "@/components/NotFoundPage";
import { PlatformRoute } from "@/components/PlatformRoute";
import { RouteFallback } from "@/components/RouteFallback";
import { SetupGate } from "@/components/SetupGate";
import { antdLocale } from "@/locales/zhCN";
import { TarkovGameModeProvider } from "@/lib/tarkovGameModeProvider";
import { antdAppTheme } from "@/theme/antdApp";

const AppLayout = lazy(() =>
  import("@/components/AppLayout").then((m) => ({ default: m.AppLayout })),
);
const SetupPage = lazy(() => import("@/pages/SetupPage"));
const LoginPage = lazy(() => import("@/pages/LoginPage"));
const LegalTermsPage = lazy(() => import("@/pages/LegalTermsPage"));
const LegalPrivacyPage = lazy(() => import("@/pages/LegalPrivacyPage"));
const RegisterPage = lazy(() => import("@/pages/RegisterPage"));
const ForgotPasswordPage = lazy(() => import("@/pages/ForgotPasswordPage"));
const VerifyEmailPage = lazy(() => import("@/pages/VerifyEmailPage"));
const SteamCalendarPage = lazy(() => import("@/pages/SteamCalendarPage"));
const SklandPage = lazy(() => import("@/pages/SklandPage"));
const TaygedoPage = lazy(() => import("@/pages/TaygedoPage"));
const ExiliumPage = lazy(() => import("@/pages/ExiliumPage"));
const KujiequPage = lazy(() => import("@/pages/KujiequPage"));
const MihoyoPage = lazy(() => import("@/pages/MihoyoPage"));
const MemberDetailPage = lazy(() => import("@/pages/MemberDetailPage"));
const MyDailyPage = lazy(() => import("@/pages/MyDailyPage"));
const ProfileSettingsPage = lazy(() => import("@/pages/ProfileSettingsPage"));
const UserManagementPage = lazy(() => import("@/pages/UserManagementPage"));
const IntegrationsSettingsPage = lazy(
  () => import("@/pages/IntegrationsSettingsPage"),
);
const AuthSettingsPage = lazy(() => import("@/pages/AuthSettingsPage"));
const EmailSettingsPage = lazy(() => import("@/pages/EmailSettingsPage"));
const TaskConfigPage = lazy(() => import("@/pages/TaskConfigPage"));
const ScheduledJobsPage = lazy(() => import("@/pages/ScheduledJobsPage"));
const PlatformLogsPage = lazy(() => import("@/pages/PlatformLogsPage"));
const SystemUpdatePage = lazy(() => import("@/pages/SystemUpdatePage"));
const TarkovGuidesOutlet = lazy(
  () => import("@/pages/guides/TarkovGuidesOutlet"),
);
const TarkovHomePage = lazy(() => import("@/pages/guides/TarkovHomePage"));
const TarkovItemsHubPage = lazy(
  () => import("@/pages/guides/TarkovItemsHubPage"),
);
const TarkovItemTypePage = lazy(
  () => import("@/pages/guides/TarkovItemTypePage"),
);
const TarkovItemDetailPage = lazy(
  () => import("@/pages/guides/TarkovItemDetailPage"),
);
const TarkovTasksPage = lazy(() => import("@/pages/guides/TarkovTasksPage"));
const TarkovRaidPrepPage = lazy(
  () => import("@/pages/guides/TarkovRaidPrepPage"),
);
const TarkovRaidRoomPage = lazy(
  () => import("@/pages/guides/TarkovRaidRoomPage"),
);
const TarkovRaidPulseDemoPage = lazy(
  () => import("@/pages/guides/TarkovRaidPulseDemoPage"),
);
const TarkovTaskDetailPage = lazy(
  () => import("@/pages/guides/TarkovTaskDetailPage"),
);
const TarkovTradersPage = lazy(() => import("@/pages/guides/TarkovTradersPage"));
const TarkovTraderPage = lazy(() => import("@/pages/guides/TarkovTraderPage"));
const TarkovBossesPage = lazy(() => import("@/pages/guides/TarkovBossesPage"));
const TarkovBossPage = lazy(() => import("@/pages/guides/TarkovBossPage"));
const TarkovMapsPage = lazy(() => import("@/pages/guides/TarkovMapsPage"));
const TarkovMapDetailPage = lazy(
  () => import("@/pages/guides/TarkovMapDetailPage"),
);
const TarkovHideoutPage = lazy(() => import("@/pages/guides/TarkovHideoutPage"));
const TarkovHideoutDetailPage = lazy(
  () => import("@/pages/guides/TarkovHideoutDetailPage"),
);
const TarkovBartersPage = lazy(() => import("@/pages/guides/TarkovBartersPage"));
const TarkovCraftsPage = lazy(() => import("@/pages/guides/TarkovCraftsPage"));
const TarkovLootTiersPage = lazy(
  () => import("@/pages/guides/TarkovLootTiersPage"),
);
const TarkovHideoutCostPage = lazy(
  () => import("@/pages/guides/TarkovHideoutCostPage"),
);
const TarkovWipeLengthPage = lazy(
  () => import("@/pages/guides/TarkovWipeLengthPage"),
);
const TarkovBitcoinFarmPage = lazy(
  () => import("@/pages/guides/TarkovBitcoinFarmPage"),
);
const TarkovMePage = lazy(() => import("@/pages/guides/TarkovMePage"));
const TarkovKeyPacksPage = lazy(
  () => import("@/pages/guides/TarkovKeyPacksPage"),
);
const TarkovGameLogsPage = lazy(
  () => import("@/pages/guides/TarkovGameLogsPage"),
);
const TarkovCollectionPage = lazy(
  () => import("@/pages/guides/TarkovCollectionPage"),
);
const TarkovProgressionPage = lazy(
  () => import("@/pages/guides/TarkovProgressionPage"),
);
const MinecraftPage = lazy(() => import("@/pages/guides/MinecraftPage"));

function AdminPage({ children }: { children: ReactNode }) {
  return <AdminRoute>{children}</AdminRoute>;
}

export default function App() {
  return (
    <ConfigProvider
      locale={{
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
      }}
      theme={antdAppTheme}
    >
      <BrowserRouter>
        <SetupGate>
          <Suspense fallback={<RouteFallback />}>
            <Routes>
              <Route path="/setup" element={<SetupPage />} />
              <Route path="/login" element={<LoginPage />} />
              <Route path="/legal/terms" element={<LegalTermsPage />} />
              <Route path="/legal/privacy" element={<LegalPrivacyPage />} />
              <Route path="/register" element={<RegisterPage />} />
              <Route
                path="/forgot-password"
                element={<ForgotPasswordPage />}
              />
              <Route path="/verify-email" element={<VerifyEmailPage />} />
              <Route
                element={
                  <PrivateRoute>
                    <TarkovGameModeProvider>
                      <Suspense fallback={<RouteFallback />}>
                        <AppLayout />
                      </Suspense>
                    </TarkovGameModeProvider>
                  </PrivateRoute>
                }
              >
                <Route path="/" element={<HomeRedirect />} />
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
                <Route
                  path="/members/:id"
                  element={
                    <PlatformRoute featureId="steam">
                      <MemberDetailPage />
                    </PlatformRoute>
                  }
                />
                <Route path="/daily" element={<MyDailyPage />} />
                <Route path="/guides/tarkov" element={<TarkovGuidesOutlet />}>
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
                  {import.meta.env.DEV ? (
                    <Route
                      path="raid-prep/pulse-demo"
                      element={<TarkovRaidPulseDemoPage />}
                    />
                  ) : null}
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
                  <Route path="barters" element={<TarkovBartersPage />} />
                  <Route path="crafts" element={<TarkovCraftsPage />} />
                  <Route path="loot-tiers" element={<TarkovLootTiersPage />} />
                  <Route
                    path="hideout-cost"
                    element={<TarkovHideoutCostPage />}
                  />
                  <Route
                    path="wipe-length"
                    element={<TarkovWipeLengthPage />}
                  />
                  <Route
                    path="bitcoin-farm"
                    element={<TarkovBitcoinFarmPage />}
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
                <Route
                  path="/guides/minecraft"
                  element={
                    <PlatformRoute featureId="guides.minecraft">
                      <MinecraftPage />
                    </PlatformRoute>
                  }
                />
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
                  path="/settings/users"
                  element={
                    <AdminPage>
                      <UserManagementPage />
                    </AdminPage>
                  }
                />
                <Route
                  path="/settings/integrations"
                  element={
                    <AdminPage>
                      <IntegrationsSettingsPage />
                    </AdminPage>
                  }
                />
                <Route
                  path="/settings/auth"
                  element={
                    <AdminPage>
                      <AuthSettingsPage />
                    </AdminPage>
                  }
                />
                <Route
                  path="/settings/email"
                  element={
                    <AdminPage>
                      <EmailSettingsPage />
                    </AdminPage>
                  }
                />
                <Route
                  path="/settings/task-config"
                  element={
                    <AdminPage>
                      <TaskConfigPage />
                    </AdminPage>
                  }
                />
                <Route
                  path="/settings/jobs"
                  element={
                    <AdminPage>
                      <ScheduledJobsPage />
                    </AdminPage>
                  }
                />
                <Route
                  path="/settings/logs"
                  element={
                    <AdminPage>
                      <PlatformLogsPage />
                    </AdminPage>
                  }
                />
                <Route
                  path="/settings/system"
                  element={
                    <AdminPage>
                      <SystemUpdatePage />
                    </AdminPage>
                  }
                />
                <Route path="*" element={<NotFoundPage />} />
              </Route>
            </Routes>
          </Suspense>
        </SetupGate>
      </BrowserRouter>
    </ConfigProvider>
  );
}
