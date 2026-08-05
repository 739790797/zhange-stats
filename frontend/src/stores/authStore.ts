import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { User } from "@/api/types";

/**
 * Token 存 localStorage（XSS 可读）。迁 httpOnly Cookie 需后端 Set-Cookie + CSRF，
 * 见仓库 README「说明」；完成前保持 Authorization Bearer。
 */
interface AuthState {
  token: string | null;
  user: User | null;
  setAuth: (token: string, user: User) => void;
  setUser: (user: User) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      setAuth: (token, user) => set({ token, user }),
      setUser: (user) => set({ user }),
      logout: () => set({ token: null, user: null }),
    }),
    { name: "zhange-stats-auth" },
  ),
);
