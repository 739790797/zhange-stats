import { Navigate, Outlet, useLocation } from "react-router-dom";
import { ForbiddenPage } from "@/components/ForbiddenPage";
import { isAdminUser } from "@/lib/isAdminUser";
import { useAuthStore } from "@/stores/authStore";

export function PrivateRoute({ children }: { children?: React.ReactNode }) {
  const user = useAuthStore((s) => s.user);
  const location = useLocation();
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  if (children) return <>{children}</>;
  return <Outlet />;
}

export function AdminRoute({ children }: { children: React.ReactNode }) {
  const user = useAuthStore((s) => s.user);
  const location = useLocation();
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  if (!isAdminUser(user)) {
    return <ForbiddenPage />;
  }
  return <>{children}</>;
}
