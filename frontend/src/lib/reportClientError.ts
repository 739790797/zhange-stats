import { client } from "@/api/http";
import { useAuthStore } from "@/stores/authStore";

export async function reportClientError(payload: {
  message: string;
  componentStack?: string;
  pathname: string;
  requestId?: string;
  appVersion?: string;
}) {
  if (!useAuthStore.getState().user) return;
  try {
    await client.post("/client-errors", {
      message: payload.message.slice(0, 500),
      component_stack: (payload.componentStack || "").slice(0, 4000),
      pathname: payload.pathname.slice(0, 256),
      request_id: payload.requestId || null,
      app_version: payload.appVersion || null,
    });
  } catch {
    /* 上报失败不打扰用户 */
  }
}
