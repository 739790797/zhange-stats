import { ConfigProvider } from "antd";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppLayout } from "@/components/AppLayout";
import { AdminRoute, PrivateRoute } from "@/components/PrivateRoute";
import { antdLocale } from "@/locales/zhCN";
import EmailSettingsPage from "@/pages/EmailSettingsPage";
import AuthSettingsPage from "@/pages/AuthSettingsPage";
import IntegrationsSettingsPage from "@/pages/IntegrationsSettingsPage";
import LoginPage from "@/pages/LoginPage";
import MemberDetailPage from "@/pages/MemberDetailPage";
import ProfileSettingsPage from "@/pages/ProfileSettingsPage";
import RegisterPage from "@/pages/RegisterPage";
import SklandPage from "@/pages/SklandPage";
import SteamCalendarPage from "@/pages/SteamCalendarPage";
import TaygedoPage from "@/pages/TaygedoPage";
import ExiliumPage from "@/pages/ExiliumPage";
import KujiequPage from "@/pages/KujiequPage";
import SystemAdminPage from "@/pages/SystemAdminPage";
import SystemUpdatePage from "@/pages/SystemUpdatePage";
import ScheduledJobsPage from "@/pages/ScheduledJobsPage";
import UserManagementPage from "@/pages/UserManagementPage";
import VerifyEmailPage from "@/pages/VerifyEmailPage";

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
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/verify-email" element={<VerifyEmailPage />} />
          <Route
            element={
              <PrivateRoute>
                <AppLayout />
              </PrivateRoute>
            }
          >
            <Route path="/" element={<Navigate to="/steam" replace />} />
            <Route path="/steam" element={<SteamCalendarPage />} />
            <Route path="/friends" element={<Navigate to="/steam" replace />} />
            <Route path="/skland" element={<SklandPage />} />
            <Route path="/taygedo" element={<TaygedoPage />} />
            <Route path="/exilium" element={<ExiliumPage />} />
            <Route path="/kujiequ" element={<KujiequPage />} />
            <Route path="/members" element={<Navigate to="/steam" replace />} />
            <Route path="/members/:id" element={<MemberDetailPage />} />
            <Route path="/profile" element={<ProfileSettingsPage />} />
            <Route
              path="/settings"
              element={
                <AdminRoute>
                  <SystemAdminPage />
                </AdminRoute>
              }
            >
              <Route index element={<Navigate to="users" replace />} />
              <Route path="users" element={<UserManagementPage />} />
              <Route
                path="integrations"
                element={<IntegrationsSettingsPage />}
              />
              <Route path="auth" element={<AuthSettingsPage />} />
              <Route path="email" element={<EmailSettingsPage />} />
              <Route path="jobs" element={<ScheduledJobsPage />} />
              <Route path="update" element={<SystemUpdatePage />} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/steam" replace />} />
        </Routes>
      </BrowserRouter>
    </ConfigProvider>
  );
}
