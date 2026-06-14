import { Link, useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { useAuth } from "@/hooks/useAuth";
import { signupSchema, type SignupValues } from "@/schemas/auth.schema";
import { FormField } from "@/components/forms/FormField";
import { PasswordField } from "@/components/forms/PasswordField";
import { SubmitButton } from "@/components/forms/SubmitButton";
import { ROUTES } from "@/constants/routes";

export default function Signup() {
  const navigate = useNavigate();
  const { signup } = useAuth();
  const form = useForm<SignupValues>({
    resolver: zodResolver(signupSchema),
    defaultValues: { name: "", email: "", password: "", organization: "", acceptTerms: false as unknown as true },
  });

  const onSubmit = form.handleSubmit(async (values) => {
    try {
      const session = await signup.mutateAsync({
        name: values.name,
        email: values.email,
        password: values.password,
        organization: values.organization,
      });
      const isAdmin = session.user.role === "admin";
      toast.success(isAdmin ? "Admin account created." : "Account created. Welcome to NGX Intelligence.");
      navigate(isAdmin ? ROUTES.admin : ROUTES.dashboard);
    } catch (e) {
      const message = e instanceof Error ? e.message : "Unable to create account.";
      toast.error(message);
    }
  });

  return (
    <div className="space-y-7">
      <div className="space-y-1.5">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-cyan/80">Create account</p>
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Start using NGX Intelligence</h1>
        <p className="text-sm text-muted-foreground">
          Already have an account?{" "}
          <Link to={ROUTES.login} className="text-cyan hover:text-cyan-300">
            Sign in
          </Link>
        </p>
      </div>

      <form onSubmit={onSubmit} className="space-y-4">
        <FormField
          label="Full name"
          autoComplete="name"
          placeholder="Adaeze Okonkwo"
          {...form.register("name")}
          error={form.formState.errors.name?.message}
        />
        <FormField
          label="Work email"
          type="email"
          autoComplete="email"
          placeholder="you@firm.com"
          {...form.register("email")}
          error={form.formState.errors.email?.message}
        />
        <FormField
          label="Organization (optional)"
          placeholder="Firm or institution name"
          {...form.register("organization")}
          error={form.formState.errors.organization?.message}
        />
        <PasswordField
          label="Password"
          autoComplete="new-password"
          placeholder="At least 8 characters, 1 uppercase, 1 number"
          {...form.register("password")}
          error={form.formState.errors.password?.message}
        />

        <label className="flex items-start gap-2 text-xs text-muted-foreground">
          <input
            type="checkbox"
            className="mt-0.5 h-3.5 w-3.5 rounded border-border bg-surface-muted"
            {...form.register("acceptTerms")}
          />
          <span>
            I agree to the platform terms and acknowledge that NGX Intelligence is an analytics product, not a
            brokerage.
          </span>
        </label>
        {form.formState.errors.acceptTerms && (
          <p className="-mt-2 text-xs text-danger">{form.formState.errors.acceptTerms.message}</p>
        )}

        <SubmitButton loading={signup.isPending} loadingLabel="Creating account…" className="w-full" size="lg">
          Create account
        </SubmitButton>
      </form>
    </div>
  );
}
