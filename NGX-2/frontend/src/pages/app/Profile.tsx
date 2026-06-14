import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { profileSchema, type ProfileValues } from "@/schemas/profile.schema";
import { useAuth } from "@/hooks/useAuth";
import { authService } from "@/services/auth.service";
import { PageHeader } from "@/components/common/PageHeader";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { FormField } from "@/components/forms/FormField";
import { SubmitButton } from "@/components/forms/SubmitButton";
import { Label } from "@/components/ui/label";
import { formatDate } from "@/lib/format";

export default function Profile() {
  const { user, setUser } = useAuth();
  const editableRole = user?.role === "admin" ? "professional" : user?.role ?? "professional";
  const form = useForm<ProfileValues>({
    resolver: zodResolver(profileSchema),
    defaultValues: {
      name: user?.name ?? "",
      email: user?.email ?? "",
      organization: user?.organization ?? "",
      role: editableRole,
    },
  });

  const onSubmit = form.handleSubmit(async (values) => {
    try {
      const updated = await authService.updateProfile({
        name: values.name,
        email: values.email,
        organization: values.organization,
        role: values.role,
      });
      setUser(updated);
      toast.success("Profile saved.");
    } catch {
      toast.error("Profile could not be saved.");
    }
  });

  if (!user) {
    return <div className="p-6 text-sm text-muted-foreground">Not signed in.</div>;
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Profile"
        title="Account profile"
        description="Manage how you appear across NGX Intelligence."
      />

      <Card>
        <CardHeader>
          <div className="flex items-center gap-4">
            <Avatar className="h-14 w-14 text-base">
              <AvatarFallback>
                {user.name
                  .split(" ")
                  .map((p) => p[0])
                  .slice(0, 2)
                  .join("")
                  .toUpperCase()}
              </AvatarFallback>
            </Avatar>
            <div>
              <CardTitle>{user.name}</CardTitle>
              <CardDescription className="flex items-center gap-2">
                {user.email}
                <Badge variant="cyan">{user.role}</Badge>
              </CardDescription>
              <p className="mt-1 text-[11px] text-muted-foreground">Member since {formatDate(user.createdAt)}</p>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="grid gap-4 md:grid-cols-2">
            <FormField label="Full name" {...form.register("name")} error={form.formState.errors.name?.message} />
            <FormField
              label="Email"
              type="email"
              {...form.register("email")}
              error={form.formState.errors.email?.message}
            />
            <FormField
              label="Organization"
              {...form.register("organization")}
              error={form.formState.errors.organization?.message}
            />
            <div className="space-y-1.5">
              <Label>Role</Label>
              <select
                {...form.register("role")}
                className="h-11 w-full rounded-lg border border-border bg-surface-muted px-3 text-sm text-foreground"
              >
                <option value="retail">Retail investor</option>
                <option value="professional">Professional analyst</option>
                <option value="institutional">Institutional user</option>
              </select>
              {form.formState.errors.role && (
                <p className="text-xs text-danger">{form.formState.errors.role.message}</p>
              )}
            </div>
            <div className="md:col-span-2 flex justify-end">
              <SubmitButton loading={form.formState.isSubmitting} loadingLabel="Saving...">
                Save profile
              </SubmitButton>
            </div>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Security</CardTitle>
          <CardDescription>Sessions, password, and authentication.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-muted-foreground">
          <p>
            Active session: <span className="text-foreground">this browser</span>
          </p>
          <p>
            Last sign-in: <span className="text-foreground">Unavailable</span>
          </p>
          <p className="text-xs">Password change and 2FA setup will be available at general availability.</p>
        </CardContent>
      </Card>
    </div>
  );
}
