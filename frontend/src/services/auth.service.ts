import type { AuthSession, LoginRequest, SignupRequest, User } from "@/types/auth";
import { http } from "./http.client";

export interface ApiToken {
  id: string;
  name: string;
  prefix: string;
  createdAt: string;
  lastUsedAt?: string | null;
  revokedAt?: string | null;
  token?: string;
}

export const authService = {
  login: async ({ email, password }: LoginRequest): Promise<AuthSession> => {
    return http.post<AuthSession>("/auth/login", { email, password });
  },

  signup: async (input: SignupRequest): Promise<AuthSession> => {
    return http.post<AuthSession>("/auth/signup", input);
  },

  me: async (): Promise<User> => {
    return http.get<User>("/auth/me");
  },

  updateProfile: async (input: {
    name: string;
    email: string;
    organization?: string;
    role: "retail" | "professional" | "institutional";
  }): Promise<User> => {
    return http.put<User>("/profile", input);
  },

  getSettings: async (): Promise<{ settings: Record<string, boolean> }> => {
    return http.get<{ settings: Record<string, boolean> }>("/profile/settings");
  },

  updateSettings: async (settings: Record<string, boolean>): Promise<{ settings: Record<string, boolean> }> => {
    return http.put<{ settings: Record<string, boolean> }>("/profile/settings", { settings });
  },

  listApiTokens: async (): Promise<ApiToken[]> => {
    return http.get<ApiToken[]>("/api-tokens");
  },

  createApiToken: async (name: string): Promise<ApiToken> => {
    return http.post<ApiToken>("/api-tokens", { name });
  },

  revokeApiToken: async (id: string): Promise<void> => {
    return http.delete<void>(`/api-tokens/${id}`);
  },

  logout: async (): Promise<void> => {
    return http.post<void>("/auth/logout");
  },

  forgotPassword: async (email: string): Promise<{ message: string }> => {
    return http.post<{ message: string }>("/auth/forgot-password", { email });
  },
};
