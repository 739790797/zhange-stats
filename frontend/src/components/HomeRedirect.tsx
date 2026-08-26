import { Navigate } from "react-router-dom";

/** 登录后默认落到「我的日常」，而不是第一个平台页。 */
export function HomeRedirect() {
  return <Navigate to="/daily" replace />;
}
