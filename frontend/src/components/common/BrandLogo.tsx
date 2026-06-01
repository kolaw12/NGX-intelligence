import { cn } from "@/lib/cn";

interface BrandLogoProps {
  className?: string;
  compact?: boolean;
}

export function BrandLogo({ className, compact = false }: BrandLogoProps) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <div className="relative h-8 w-8 shrink-0 overflow-hidden rounded-lg bg-navy-700 ring-1 ring-cyan/30 shadow-glow">
        <svg viewBox="0 0 32 32" className="h-full w-full" aria-hidden="true">
          <rect width="32" height="32" rx="8" fill="#131E47" />
          <path d="M7 22V10h2.8l5.2 7.6V10H17.6V22H14.8L9.6 14.4V22H7Z" fill="#00DCDC" />
          <circle cx="23" cy="11" r="2" fill="#E89A35" />
        </svg>
      </div>
      {!compact && (
        <div className="leading-none">
          <div className="text-sm font-semibold tracking-tight text-foreground">NGX Intelligence</div>
          <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">Financial Intelligence</div>
        </div>
      )}
    </div>
  );
}
