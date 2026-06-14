export type UserRole = "retail" | "professional" | "institutional" | "admin";
export type UserStatus = "active" | "suspended" | "pending";

export interface User {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  status?: UserStatus;
  organization?: string;
  avatarUrl?: string;
  createdAt: string;
}

export interface AuthSession {
  token: string;
  user: User;
  expiresAt: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface SignupRequest {
  name: string;
  email: string;
  password: string;
  organization?: string;
}

export interface Alert {
  id: string;
  symbol: string;
  condition: "above" | "below" | "ai-outlook-change" | "volume-spike";
  threshold: number;
  status: "active" | "triggered" | "expired";
  createdAt: string;
  triggeredAt?: string;
  message?: string;
}
