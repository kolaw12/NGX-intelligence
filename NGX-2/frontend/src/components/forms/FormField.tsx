import * as React from "react";
import { Label } from "@/components/ui/label";
import { Input, type InputProps } from "@/components/ui/input";
import { cn } from "@/lib/cn";

interface FormFieldProps extends InputProps {
  label: string;
  error?: string;
  helperText?: string;
  containerClassName?: string;
}

export const FormField = React.forwardRef<HTMLInputElement, FormFieldProps>(
  ({ label, error, helperText, containerClassName, id, ...inputProps }, ref) => {
    const generatedId = React.useId();
    const inputId = id ?? generatedId;
    return (
      <div className={cn("space-y-1.5", containerClassName)}>
        <Label htmlFor={inputId}>{label}</Label>
        <Input id={inputId} ref={ref} aria-invalid={Boolean(error)} {...inputProps} />
        {error ? (
          <p className="text-xs text-danger">{error}</p>
        ) : helperText ? (
          <p className="text-xs text-muted-foreground">{helperText}</p>
        ) : null}
      </div>
    );
  },
);
FormField.displayName = "FormField";
