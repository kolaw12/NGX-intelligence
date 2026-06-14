import { LayoutDashboard, Users, ScrollText, type LucideIcon } from "lucide-react";
import { ROUTES } from "./routes";

export interface AdminNavItem {
  label: string;
  to: string;
  icon: LucideIcon;
  description?: string;
}

export const ADMIN_NAV: AdminNavItem[] = [
  { label: "Overview", to: ROUTES.adminOverview, icon: LayoutDashboard, description: "Platform metrics & health" },
  { label: "Users", to: ROUTES.adminUsers, icon: Users, description: "Manage platform users" },
  { label: "Activity", to: ROUTES.adminActivity, icon: ScrollText, description: "Audit log" },
];
