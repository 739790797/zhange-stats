import type { AxiosError } from "axios";
import { client } from "@/shared/api/http";
import { isUnsafeHttpMethod, readCsrfToken } from "@/shared/api/csrfCookie";
import { handleHttpError } from "./httpErrorHandler";
import { handleTarkovResponse, prepareTarkovRequest } from "@/features/guides/tarkov/api/httpIntegration";
import { markAxiosRumStart, recordAxiosRum } from "@/app/telemetry/httpAxios";

let installed = false;

export function installClientInterceptors() {
  if (installed) return;
  installed = true;

  client.interceptors.request.use(async (config) => {
    markAxiosRumStart(config);
    if (isUnsafeHttpMethod(config.method)) {
      const csrf = readCsrfToken();
      if (csrf) config.headers["X-CSRF-Token"] = csrf;
    }
    return prepareTarkovRequest(config);
  });

  client.interceptors.response.use(
    async (res) => {
      recordAxiosRum(res.config, res.status);
      return handleTarkovResponse(res, client);
    },
    (error: AxiosError) => handleHttpError(error),
  );
}
