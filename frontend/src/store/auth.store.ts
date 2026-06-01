import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { AuthSession, User } from "@/types/auth";

interface AuthState {
  user: User | null;
  token: string | null;
  expiresAt: string | null;
  isHydrated: boolean;
  setSession: (session: AuthSession) => void;
  setUser: (user: User) => void;
  clear: () => void;
  setHydrated: () => void;
  isAuthenticated: () => boolean;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      expiresAt: null,
      isHydrated: false,
      setSession: (session) =>
        set({ user: session.user, token: session.token, expiresAt: session.expiresAt }),
      setUser: (user) => set({ user }),
      clear: () => set({ user: null, token: null, expiresAt: null }),
      setHydrated: () => set({ isHydrated: true }),
      isAuthenticated: () => {
        const { token, expiresAt } = get();
        if (!token || !expiresAt) return false;
        return new Date(expiresAt).getTime() > Date.now();
      },
    }),
    {
      name: "ngx.auth",
      partialize: (state) => ({
        user: state.user,
        token: state.token,
        expiresAt: state.expiresAt,
      }),
      onRehydrateStorage: () => (state) => {
        state?.setHydrated();
      },
    },
  ),
);
