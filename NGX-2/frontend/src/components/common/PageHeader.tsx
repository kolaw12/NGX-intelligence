import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

interface PageHeaderProps {
  title: string;
  description?: string;
  actions?: ReactNode;
  eyebrow?: string;
  className?: string;
}

export function PageHeader({ title, description, actions, eyebrow, className }: PageHeaderProps) {
  return (
    <div
      className={cn(
        "flex flex-col gap-3 border-b border-border pb-5 md:flex-row md:items-end md:justify-between",
        className,
      )}
    >
      <div className="space-y-1">
        {eyebrow && (
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-cyan/80">{eyebrow}</p>
        )}
        <h1 className="text-2xl font-semibold tracking-tight text-foreground md:text-display-lg">{title}</h1>
        {description && <p className="max-w-3xl text-sm text-muted-foreground">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
