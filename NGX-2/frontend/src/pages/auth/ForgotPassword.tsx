import { Link } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { useAuth } from "@/hooks/useAuth";
import { forgotPasswordSchema, type ForgotPasswordValues } from "@/schemas/auth.schema";
import { FormField } from "@/components/forms/FormField";
import { SubmitButton } from "@/components/forms/SubmitButton";
import { ROUTES } from "@/constants/routes";

export default function ForgotPassword() {
  const { forgotPassword } = useAuth();
  const form = useForm<ForgotPasswordValues>({
    resolver: zodResolver(forgotPasswordSchema),
    defaultValues: { email: "" },
  });

  const onSubmit = form.handleSubmit(async ({ email }) => {
    try {
      const res = await forgotPassword.mutateAsync(email);
      toast.success(res.message);
      form.reset();
    } catch (e) {
      const message = e instanceof Error ? e.message : "Unable to send reset instructions.";
      toast.error(message);
    }
  });

  return (
    <div className="space-y-7">
      <div className="space-y-1.5">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-cyan/80">Account recovery</p>
        <h1 className="text-2xl font-semibold tracking-tight text-foreground">Reset your password</h1>
        <p className="text-sm text-muted-foreground">
          We'll send instructions to your email if an account exists.
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
        <SubmitButton
          loading={forgotPassword.isPending}
          loadingLabel="Sending…"
          className="w-full"
          size="lg"
        >
          Send reset link
        </SubmitButton>
      </form>

      <p className="text-xs text-muted-foreground">
        Remembered your password?{" "}
        <Link to={ROUTES.login} className="text-cyan hover:text-cyan-300">
          Back to sign in
        </Link>
      </p>
    </div>
  );
}
