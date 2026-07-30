import { ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppLayout } from "@/components/AppLayout";
import { AdminRoute, PrivateRoute } from "@/components/PrivateRoute";
import EmailSettingsPage from "@/pages/EmailSettingsPage";
import LoginPage from "@/pages/LoginPage";
import MemberDetailPage from "@/pages/MemberDetailPage";
import MemberProfilePage from "@/pages/MemberProfilePage";
import MembersPage from "@/pages/MembersPage";
import OverviewPage from "@/pages/OverviewPage";
import ProfileSettingsPage from "@/pages/ProfileSettingsPage";
import RegisterPage from "@/pages/RegisterPage";
import SteamCalendarPage from "@/pages/SteamCalendarPage";
import UserManagementPage from "@/pages/UserManagementPage";
import VerifyEmailPage from "@/pages/VerifyEmailPage";

export default function App() {
  return (
    <ConfigProvider
      locale={zhCN}
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
            <Route path="/" element={<OverviewPage />} />
            <Route path="/members" element={<MembersPage />} />
            <Route path="/members/:id" element={<MemberDetailPage />} />
            <Route path="/members/:id/profile" element={<MemberProfilePage />} />
            <Route path="/steam" element={<SteamCalendarPage />} />
            <Route path="/profile" element={<ProfileSettingsPage />} />
            <Route
              path="/settings"
              element={<Navigate to="/settings/users" replace />}
            />
            <Route
              path="/settings/users"
              element={
                <AdminRoute>
                  <UserManagementPage />
                </AdminRoute>
              }
            />
            <Route
              path="/settings/email"
              element={
                <AdminRoute>
                  <EmailSettingsPage />
                </AdminRoute>
              }
            />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </ConfigProvider>
  );
}
