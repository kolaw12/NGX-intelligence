import { Loader2 } from "lucide-react";
import { Button, type ButtonProps } from "@/components/ui/button";

interface SubmitButtonProps extends ButtonProps {
  loading?: boolean;
  loadingLabel?: string;
}

export function SubmitButton({ loading, loadingLabel, children, disabled, ...rest }: SubmitButtonProps) {
  return (
    <Button type="submit" disabled={loading || disabled} {...rest}>
      {loading && <Loader2 className="h-4 w-4 animate-spin" />}
      {loading ? loadingLabel ?? "Please wait" : children}
    </Button>
  );
}
