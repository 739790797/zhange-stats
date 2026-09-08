import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { User } from "@/api/types";

/** 登录态以 HttpOnly Cookie 为准；这里只持久化用户资料供壳层展示。 */
interface AuthState {
  user: User | null;
  setUser: (user: User) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      setUser: (user) => set({ user }),
      logout: () => set({ user: null }),
    }),
    {
      name: "zhange-stats-auth",
      partialize: (s) => ({ user: s.user }),
    },
  ),
);
