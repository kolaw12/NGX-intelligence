import type { AIOutlook } from "@/types/stock";
import { Badge } from "@/components/ui/badge";
import { TrendingUp, TrendingDown, Minus, BrainCircuit } from "lucide-react";

interface PredictionBadgeProps {
  outlook: AIOutlook;
  withLabel?: boolean;
  withIcon?: boolean;
  variant?: "filled" | "outline";
}

const ICON = {
  bullish: TrendingUp,
  bearish: TrendingDown,
  neutral: Minus,
};

const VARIANT_MAP: Record<AIOutlook, "success" | "danger" | "default"> = {
  bullish: "success",
  bearish: "danger",
  neutral: "default",
};

export function PredictionBadge({ outlook, withLabel = true, withIcon = true }: PredictionBadgeProps) {
  const Icon = ICON[outlook];
  return (
    <Badge variant={VARIANT_MAP[outlook]} className="capitalize">
      {withIcon && <BrainCircuit className="h-3 w-3" />}
      {withLabel && (
        <span className="inline-flex items-center gap-1">
          <Icon className="h-3 w-3" />
          {outlook}
        </span>
      )}
    </Badge>
  );
}
