import axios from "axios";
import { useAuthStore } from "@/stores/authStore";

export const client = axios.create({
  baseURL: "/api",
  timeout: 15000,
});

client.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

client.interceptors.response.use(
  (res) => res,
  (error) => {
    const url = String(error.config?.url || "");
    const isLoginAttempt = url.includes("/auth/login");
    const status = error.response?.status;
    const code = error.response?.data?.code;
    if (status === 503 && code === "SETUP_REQUIRED") {
      if (typeof window !== "undefined" && !window.location.pathname.startsWith("/setup")) {
        window.location.assign("/setup");
      }
      return Promise.reject(error);
    }
    if (status === 401 && !isLoginAttempt) {
      useAuthStore.getState().logout();
    }
    return Promise.reject(error);
  },
);
