import type { User, UserRole, UserStatus } from "./auth";

export interface AdminUser extends User {
  status: UserStatus;
  lastLoginAt?: string;
  totalLogins: number;
  watchlistCount: number;
  alertCount: number;
  countryCode?: string;
}

export type ActivityEventType =
  | "login"
  | "logout"
  | "signup"
  | "alert.create"
  | "alert.delete"
  | "alert.triggered"
  | "watchlist.create"
  | "watchlist.update"
  | "watchlist.delete"
  | "profile.update"
  | "password.reset"
  | "admin.user.suspend"
  | "admin.user.activate"
  | "admin.user.role-change";

export interface ActivityEvent {
  id: string;
  userId: string;
  userEmail: string;
  userName: string;
  type: ActivityEventType;
  description: string;
  ip?: string;
  userAgent?: string;
  timestamp: string;
  metadata?: Record<string, string | number>;
}

export interface AdminMetrics {
  totalUsers: number;
  activeUsers: number;
  suspendedUsers: number;
  newSignupsToday: number;
  newSignups7d: number;
  dau: number;
  mau: number;
  totalAlerts: number;
  activeAlerts: number;
  triggeredAlertsToday: number;
  totalWatchlists: number;
  apiRequests24h: number;
  apiErrorRate24h: number;
  signupsSeries: { date: string; count: number }[];
  dauSeries: { date: string; count: number }[];
  roleBreakdown: { role: UserRole; count: number }[];
}

export interface UpdateUserRequest {
  role?: UserRole;
  status?: UserStatus;
}
