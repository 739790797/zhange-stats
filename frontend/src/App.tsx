import type { ReactNode } from "react";
import { ConfigProvider } from "antd";
import { BrowserRouter, Navigate, Outlet, Route, Routes } from "react-router-dom";
import { AppLayout } from "@/components/AppLayout";
import { AdminRoute, PrivateRoute } from "@/components/PrivateRoute";
import { SetupGate } from "@/components/SetupGate";
import { antdLocale } from "@/locales/zhCN";
import EmailSettingsPage from "@/pages/EmailSettingsPage";
import AuthSettingsPage from "@/pages/AuthSettingsPage";
import IntegrationsSettingsPage from "@/pages/IntegrationsSettingsPage";
import LoginPage from "@/pages/LoginPage";
import MemberDetailPage from "@/pages/MemberDetailPage";
import MyDailyPage from "@/pages/MyDailyPage";
import ProfileSettingsPage from "@/pages/ProfileSettingsPage";
import RegisterPage from "@/pages/RegisterPage";
import ForgotPasswordPage from "@/pages/ForgotPasswordPage";
import SetupPage from "@/pages/SetupPage";
import SklandPage from "@/pages/SklandPage";
import SteamCalendarPage from "@/pages/SteamCalendarPage";
import TaygedoPage from "@/pages/TaygedoPage";
import ExiliumPage from "@/pages/ExiliumPage";
import KujiequPage from "@/pages/KujiequPage";
import MihoyoPage from "@/pages/MihoyoPage";
import ScheduledJobsPage from "@/pages/ScheduledJobsPage";
import TaskConfigPage from "@/pages/TaskConfigPage";
import UserManagementPage from "@/pages/UserManagementPage";
import QqGroupsPage from "@/pages/QqGroupsPage";
import SystemUpdatePage from "@/pages/SystemUpdatePage";
import PlatformLogsPage from "@/pages/PlatformLogsPage";
import VerifyEmailPage from "@/pages/VerifyEmailPage";
import TarkovHomePage from "@/pages/guides/TarkovHomePage";
import TarkovItemsHubPage from "@/pages/guides/TarkovItemsHubPage";
import TarkovItemTypePage from "@/pages/guides/TarkovItemTypePage";
import TarkovItemDetailPage from "@/pages/guides/TarkovItemDetailPage";
import TarkovTasksPage from "@/pages/guides/TarkovTasksPage";
import TarkovTaskDetailPage from "@/pages/guides/TarkovTaskDetailPage";
import TarkovTradersPage from "@/pages/guides/TarkovTradersPage";
import TarkovTraderPage from "@/pages/guides/TarkovTraderPage";
import TarkovBossesPage from "@/pages/guides/TarkovBossesPage";
import TarkovBossPage from "@/pages/guides/TarkovBossPage";
import TarkovMapsPage from "@/pages/guides/TarkovMapsPage";
import TarkovMapDetailPage from "@/pages/guides/TarkovMapDetailPage";
import TarkovHideoutPage from "@/pages/guides/TarkovHideoutPage";
import TarkovHideoutDetailPage from "@/pages/guides/TarkovHideoutDetailPage";
import TarkovBartersPage from "@/pages/guides/TarkovBartersPage";
import TarkovCraftsPage from "@/pages/guides/TarkovCraftsPage";
import TarkovLootTiersPage from "@/pages/guides/TarkovLootTiersPage";
import TarkovHideoutCostPage from "@/pages/guides/TarkovHideoutCostPage";
import TarkovWipeLengthPage from "@/pages/guides/TarkovWipeLengthPage";
import TarkovBitcoinFarmPage from "@/pages/guides/TarkovBitcoinFarmPage";
import TarkovProgressionPage from "@/pages/guides/TarkovProgressionPage";
import MinecraftPage from "@/pages/guides/MinecraftPage";
import { HomeRedirect } from "@/components/HomeRedirect";
import { PlatformRoute } from "@/components/PlatformRoute";
import { TarkovGuideShell } from "@/components/guides/tarkov/TarkovGuideShell";

function TarkovGuidesOutlet() {
  return (
    <PlatformRoute featureId="guides.tarkov">
      <TarkovGuideShell>
        <Outlet />
      </TarkovGuideShell>
    </PlatformRoute>
  );
}

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
      theme={{
        token: {
          colorPrimary: "#1a2332",
          colorLink: "#2f6f4e",
          borderRadius: 6,
          fontFamily:
            '"Source Han Sans SC", "Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif',
        },
      }}
    >
      <BrowserRouter>
        <SetupGate>
          <Routes>
            <Route path="/setup" element={<SetupPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/forgot-password" element={<ForgotPasswordPage />} />
            <Route path="/verify-email" element={<VerifyEmailPage />} />
            <Route
              element={
                <PrivateRoute>
                  <AppLayout />
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
                <Route path="maps" element={<TarkovMapsPage />} />
                <Route path="maps/:mapSlug" element={<TarkovMapDetailPage />} />
                <Route
                  path="traders"
                  element={<TarkovTradersPage />}
                />
                <Route
                  path="traders/:traderSlug"
                  element={<TarkovTraderPage />}
                />
                <Route
                  path="bosses"
                  element={<TarkovBossesPage />}
                />
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
                path="/settings/qq-groups"
                element={
                  <AdminPage>
                    <QqGroupsPage />
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
            </Route>
            <Route path="*" element={<HomeRedirect />} />
          </Routes>
        </SetupGate>
      </BrowserRouter>
    </ConfigProvider>
  );
}
