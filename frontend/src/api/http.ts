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
    // 登录接口的 401 是凭据错误，不要清掉本地会话以外的状态误伤
    const url = String(error.config?.url || "");
    const isLoginAttempt = url.includes("/auth/login");
    if (error.response?.status === 401 && !isLoginAttempt) {
      useAuthStore.getState().logout();
    }
    return Promise.reject(error);
  },
);
