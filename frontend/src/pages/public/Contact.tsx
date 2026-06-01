import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { contactSchema, type ContactValues } from "@/schemas/profile.schema";
import { Badge } from "@/components/ui/badge";
import { FormField } from "@/components/forms/FormField";
import { SubmitButton } from "@/components/forms/SubmitButton";
import { Label } from "@/components/ui/label";
import { Mail, Phone, MapPin } from "lucide-react";

const contactBlocks = [
  { icon: Mail, label: "Email", value: "intelligence@ngx-intel.app" },
  { icon: Phone, label: "Phone", value: "+234 (0) 1 700 0000" },
  { icon: MapPin, label: "Office", value: "Victoria Island, Lagos, Nigeria" },
];

export default function Contact() {
  const form = useForm<ContactValues>({
    resolver: zodResolver(contactSchema),
    defaultValues: { name: "", email: "", organization: "", message: "" },
  });

  const onSubmit = form.handleSubmit(async (values) => {
    const subject = encodeURIComponent(`NGX Intelligence enquiry from ${values.organization || values.name}`);
    const body = encodeURIComponent(`${values.message}\n\n${values.name}\n${values.email}`);
    window.location.href = `mailto:intelligence@ngx-intel.app?subject=${subject}&body=${body}`;
    toast.message("Opening your email client. The website did not submit this as a backend message.");
  });

  return (
    <div>
      <section className="bg-radial-light">
        <div className="container py-16 md:py-24">
          <div className="max-w-2xl">
            <Badge variant="cyan">Contact</Badge>
            <h1 className="mt-5 text-display-xl font-semibold tracking-tight text-foreground">
              Let's talk financial intelligence
            </h1>
            <p className="mt-4 text-base leading-relaxed text-muted-foreground sm:text-lg">
              Whether you're an analyst, a fintech, or an institutional team — we'd love to understand your workflows and
              how the platform can support them.
            </p>
          </div>
        </div>
      </section>

      <section className="container grid gap-10 py-16 lg:grid-cols-[1fr,1.2fr]">
        <div className="space-y-5">
          {contactBlocks.map((b) => (
            <div key={b.label} className="flex items-start gap-3 rounded-xl border border-border bg-surface/80 p-4">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-cyan/15 text-cyan ring-1 ring-cyan/30">
                <b.icon className="h-4 w-4" />
              </div>
              <div>
                <p className="text-[11px] uppercase tracking-wider text-muted-foreground">{b.label}</p>
                <p className="text-sm font-semibold text-foreground">{b.value}</p>
              </div>
            </div>
          ))}
          <div className="rounded-xl border border-border bg-surface/60 p-5 text-sm text-muted-foreground">
            <p className="font-semibold text-foreground">Office hours</p>
            <p className="mt-1">Mon — Fri · 9:00 — 17:00 WAT</p>
            <p className="mt-3 text-xs">Responses within one business day.</p>
          </div>
        </div>

        <form onSubmit={onSubmit} className="space-y-4 rounded-xl border border-border bg-surface/80 p-6">
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField
              label="Full name"
              placeholder="Adaeze Okonkwo"
              {...form.register("name")}
              error={form.formState.errors.name?.message}
            />
            <FormField
              label="Email"
              type="email"
              placeholder="you@firm.com"
              {...form.register("email")}
              error={form.formState.errors.email?.message}
            />
          </div>
          <FormField
            label="Organization (optional)"
            placeholder="Firm or institution name"
            {...form.register("organization")}
            error={form.formState.errors.organization?.message}
          />
          <div className="space-y-1.5">
            <Label>Message</Label>
            <textarea
              {...form.register("message")}
              placeholder="Tell us about your team and what you're hoping to do with NGX Intelligence."
              rows={5}
              className="flex w-full rounded-lg border border-border bg-surface-muted px-3.5 py-2.5 text-sm text-foreground placeholder:text-muted-foreground/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan/60"
              aria-invalid={Boolean(form.formState.errors.message)}
            />
            {form.formState.errors.message && (
              <p className="text-xs text-danger">{form.formState.errors.message.message}</p>
            )}
          </div>
          <SubmitButton loading={form.formState.isSubmitting} loadingLabel="Sending…" className="w-full">
            Send message
          </SubmitButton>
          <p className="text-[11px] text-muted-foreground">
            By contacting us you agree to the platform's privacy policy. We will only use your details to respond to
            this enquiry.
          </p>
        </form>
      </section>
    </div>
  );
}
