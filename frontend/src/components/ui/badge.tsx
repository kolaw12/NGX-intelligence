/* eslint-disable react-refresh/only-export-components */
import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/cn";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-medium tracking-wide",
  {
    variants: {
      variant: {
        default: "bg-surface-elevated text-muted-foreground border border-border",
        cyan: "bg-cyan/10 text-cyan border border-cyan/30",
        gold: "bg-gold/12 text-gold border border-gold/30",
        success: "bg-success-soft text-success border border-success/30",
        danger: "bg-danger-soft text-danger border border-danger/30",
        warning: "bg-warning-soft text-warning border border-warning/30",
        royal: "bg-navy text-white border border-navy",
        outline: "border border-border text-muted-foreground",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { badgeVariants };
