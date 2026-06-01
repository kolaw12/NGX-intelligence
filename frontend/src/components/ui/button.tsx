/* eslint-disable react-refresh/only-export-components */
import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/cn";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-sm font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan/60 focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        primary:
          "bg-navy text-white hover:bg-navy-800 shadow-[0_8px_24px_-12px_rgba(19,30,71,0.45)] hover:shadow-[0_12px_32px_-12px_rgba(19,30,71,0.6)]",
        secondary:
          "bg-surface-elevated text-foreground border border-border hover:bg-muted",
        outline:
          "border border-border bg-surface text-foreground hover:bg-surface-elevated hover:border-border-strong",
        ghost: "text-muted-foreground hover:text-foreground hover:bg-surface-elevated",
        danger: "bg-danger text-white hover:bg-danger/90",
        link: "text-cyan-700 hover:text-cyan-800 underline-offset-4 hover:underline",
        cyan: "bg-cyan text-navy-900 hover:bg-cyan-400 shadow-[0_8px_24px_-12px_rgba(0,220,220,0.45)] hover:shadow-[0_12px_32px_-12px_rgba(0,220,220,0.6)]",
      },
      size: {
        sm: "h-8 px-3 text-xs",
        md: "h-10 px-4",
        lg: "h-12 px-6 text-base",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return (
      <Comp className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />
    );
  },
);
Button.displayName = "Button";

export { buttonVariants };
