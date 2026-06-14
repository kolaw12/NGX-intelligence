import { lazy, Suspense } from "react";
import { Routes, Route } from "react-router-dom";
import { ProtectedRoute } from "./ProtectedRoute";
import { PublicOnlyRoute } from "./PublicOnlyRoute";
import { AdminProtectedRoute } from "./AdminProtectedRoute";
import { PublicLayout } from "@/components/layouts/PublicLayout";
import { AuthLayout } from "@/components/layouts/AuthLayout";
import { AppLayout } from "@/components/layouts/AppLayout";
import { AdminLayout } from "@/components/layouts/AdminLayout";
import { PageSkeleton } from "@/components/common/LoadingSkeleton";
import { ROUTES } from "@/constants/routes";

const Landing = lazy(() => import("@/pages/public/Landing"));
const Features = lazy(() => import("@/pages/public/Features"));
const About = lazy(() => import("@/pages/public/About"));
const Contact = lazy(() => import("@/pages/public/Contact"));
const NotFound = lazy(() => import("@/pages/public/NotFound"));

const Login = lazy(() => import("@/pages/auth/Login"));
const Signup = lazy(() => import("@/pages/auth/Signup"));
const ForgotPassword = lazy(() => import("@/pages/auth/ForgotPassword"));

const Dashboard = lazy(() => import("@/pages/app/Dashboard"));
const Markets = lazy(() => import("@/pages/app/Markets"));
const Sectors = lazy(() => import("@/pages/app/Sectors"));
const SectorDetail = lazy(() => import("@/pages/app/SectorDetail"));
const Stocks = lazy(() => import("@/pages/app/Stocks"));
const StockDetail = lazy(() => import("@/pages/app/StockDetail"));
const AIInsights = lazy(() => import("@/pages/app/AIInsights"));
const Portfolio = lazy(() => import("@/pages/app/Portfolio"));
const Watchlists = lazy(() => import("@/pages/app/Watchlists"));
const Alerts = lazy(() => import("@/pages/app/Alerts"));
const Settings = lazy(() => import("@/pages/app/Settings"));
const Profile = lazy(() => import("@/pages/app/Profile"));

const AdminOverview = lazy(() => import("@/pages/admin/Overview"));
const AdminUsers = lazy(() => import("@/pages/admin/Users"));
const AdminActivity = lazy(() => import("@/pages/admin/Activity"));

export function AppRoutes() {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <Routes>
        {/* Public marketing */}
        <Route element={<PublicLayout />}>
          <Route path={ROUTES.home} element={<Landing />} />
          <Route path={ROUTES.features} element={<Features />} />
          <Route path={ROUTES.about} element={<About />} />
          <Route path={ROUTES.contact} element={<Contact />} />
        </Route>

        {/* Auth (public-only) */}
        <Route element={<PublicOnlyRoute />}>
          <Route element={<AuthLayout />}>
            <Route path={ROUTES.login} element={<Login />} />
            <Route path={ROUTES.signup} element={<Signup />} />
            <Route path={ROUTES.forgotPassword} element={<ForgotPassword />} />
          </Route>
        </Route>

        {/* User app (any authenticated role) */}
        <Route element={<ProtectedRoute />}>
          <Route element={<AppLayout />}>
            <Route path={ROUTES.dashboard} element={<Dashboard />} />
            <Route path={ROUTES.markets} element={<Markets />} />
            <Route path={ROUTES.sectors} element={<Sectors />} />
            <Route path="/app/sectors/:slug" element={<SectorDetail />} />
            <Route path={ROUTES.stocks} element={<Stocks />} />
            <Route path="/app/stocks/:symbol" element={<StockDetail />} />
            <Route path={ROUTES.aiInsights} element={<AIInsights />} />
            <Route path={ROUTES.portfolio} element={<Portfolio />} />
            <Route path={ROUTES.watchlists} element={<Watchlists />} />
            <Route path={ROUTES.alerts} element={<Alerts />} />
            <Route path={ROUTES.settings} element={<Settings />} />
            <Route path={ROUTES.profile} element={<Profile />} />
          </Route>
        </Route>

        {/* Admin portal (admin role only) */}
        <Route element={<AdminProtectedRoute />}>
          <Route element={<AdminLayout />}>
            <Route path={ROUTES.adminOverview} element={<AdminOverview />} />
            <Route path={ROUTES.adminUsers} element={<AdminUsers />} />
            <Route path={ROUTES.adminActivity} element={<AdminActivity />} />
          </Route>
        </Route>

        <Route path="*" element={<NotFound />} />
      </Routes>
    </Suspense>
  );
}
