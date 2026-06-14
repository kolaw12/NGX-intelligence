import { useMutation, useQueryClient } from "@tanstack/react-query";
import { authService } from "@/services/auth.service";
import { useAuthStore } from "@/store/auth.store";
import type { LoginRequest, SignupRequest } from "@/types/auth";

export function useAuth() {
  const session = useAuthStore();
  const qc = useQueryClient();

  const login = useMutation({
    mutationFn: (input: LoginRequest) => authService.login(input),
    onSuccess: (result) => {
      session.setSession(result);
    },
  });

  const signup = useMutation({
    mutationFn: (input: SignupRequest) => authService.signup(input),
    onSuccess: (result) => {
      session.setSession(result);
    },
  });

  const logout = useMutation({
    mutationFn: () => authService.logout(),
    onSuccess: () => {
      session.clear();
      qc.clear();
    },
  });

  const forgotPassword = useMutation({
    mutationFn: (email: string) => authService.forgotPassword(email),
  });

  return {
    user: session.user,
    token: session.token,
    setUser: session.setUser,
    isAuthenticated: session.isAuthenticated(),
    isHydrated: session.isHydrated,
    login,
    signup,
    logout,
    forgotPassword,
  };
}
