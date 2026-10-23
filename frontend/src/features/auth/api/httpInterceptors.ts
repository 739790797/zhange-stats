import { useAuthStore } from "@/features/auth/model/authStore";
import {
  resetLogoutOnce,
  shouldLogoutOn401,
  takeLogoutOnce,
} from "@/features/auth/model/shouldLogoutOn401";

/** fetch 流式接口与 axios 拦截器共用：已登录业务 401 只登出一次。 */
export function notifyUnauthorized(status: number, url: string) {
  const hasSession = Boolean(useAuthStore.getState().user);
  if (
    shouldLogoutOn401({
      status,
      url,
      hasSession,
    }) &&
    takeLogoutOnce()
  ) {
    void import("./authApi")
      .then((m) => m.logoutRequest())
      .catch(() => {
        /* 会话已失效时 logout 仍可能 401/403，本地照样清掉 */
      })
      .finally(() => {
        useAuthStore.getState().logout();
      });
    window.setTimeout(() => resetLogoutOnce(), 1500);
  }
}
