import { Link, useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { useAuth } from "@/hooks/useAuth";
import { loginSchema, type LoginValues } from "@/schemas/auth.schema";
import { FormField } from "@/components/forms/FormField";
import { PasswordField } from "@/components/forms/PasswordField";
import { SubmitButton } from "@/components/forms/SubmitButton";
import { ROUTES } from "@/constants/routes";

export default function Login() {
  const navigate = useNavigate();
  const { login } = useAuth();
  const form = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });

  const onSubmit = form.handleSubmit(async (values) => {
    try {
      const session = await login.mutateAsync(values);
      const isAdmin = session.user.role === "admin";
      toast.success(isAdmin ? "Signed in to the admin portal." : "Welcome back to NGX Intelligence.");
      navigate(isAdmin ? ROUTES.admin : ROUTES.dashboard);
    } catch (e) {
      const message = e instanceof Error ? e.message : "Unable to sign in.";
      toast.error(message);
    }
  });

  return (
    <div className="space-y-7">
      <div className="space-y-1.5">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-cyan/80">Sign in</p>
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Welcome back</h1>
        <p className="text-sm text-muted-foreground">
          Don't have an account?{" "}
          <Link to={ROUTES.signup} className="text-cyan hover:text-cyan-300">
            Create one
          </Link>
        </p>
      </div>

      <form onSubmit={onSubmit} className="space-y-4">
        <FormField
          label="Email"
          type="email"
          autoComplete="email"
          placeholder="you@firm.com"
          {...form.register("email")}
          error={form.formState.errors.email?.message}
        />
        <PasswordField
          label="Password"
          autoComplete="current-password"
          placeholder="••••••••"
          {...form.register("password")}
          error={form.formState.errors.password?.message}
        />

        <div className="flex items-center justify-between text-xs">
          <label className="flex items-center gap-2 text-muted-foreground">
            <input type="checkbox" className="h-3.5 w-3.5 rounded border-border bg-surface-muted" /> Remember this device
          </label>
          <Link to={ROUTES.forgotPassword} className="text-cyan hover:text-cyan-300">
            Forgot password?
          </Link>
        </div>

        <SubmitButton loading={login.isPending} loadingLabel="Signing in…" className="w-full" size="lg">
          Sign in
        </SubmitButton>
      </form>

      <div className="space-y-2 rounded-lg border border-dashed border-border bg-surface-elevated/60 p-3 text-[11px] text-muted-foreground">
        <p className="font-semibold text-foreground">Demo access</p>
        <p>
          Use any email + an 8+ character password. Emails starting with <span className="font-mono text-foreground">admin</span>
          {" "}(e.g. <span className="font-mono text-foreground">admin@ngx-intel.app</span>) route to the admin portal.
        </p>
      </div>

      <p className="text-[11px] text-muted-foreground">
        By signing in, you accept our terms of service and acknowledge that NGX Intelligence is an analytics platform —
        not a brokerage.
      </p>
    </div>
  );
}
