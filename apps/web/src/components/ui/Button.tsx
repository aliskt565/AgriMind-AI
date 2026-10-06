import { ButtonHTMLAttributes, forwardRef } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  isLoading?: boolean;
}

const variantClasses: Record<Variant, string> = {
  primary:
    "bg-[var(--color-brand)] text-white shadow-[var(--shadow-sm)] hover:bg-[var(--color-brand-strong)] hover:shadow-[var(--shadow-glow-brand)] hover:-translate-y-px active:translate-y-0 active:shadow-[var(--shadow-sm)] disabled:opacity-50 disabled:hover:translate-y-0 disabled:hover:shadow-[var(--shadow-sm)]",
  secondary:
    "bg-transparent border border-[var(--color-border-strong)] text-[var(--color-text-primary)] hover:bg-[var(--color-surface-hover)] hover:border-[var(--color-brand)] hover:-translate-y-px active:translate-y-0 disabled:opacity-50 disabled:hover:translate-y-0",
  ghost:
    "bg-transparent text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-hover)] hover:text-[var(--color-text-primary)] disabled:opacity-50",
  danger:
    "bg-transparent border border-[var(--color-status-critical)]/40 text-[var(--color-status-critical)] hover:bg-[var(--color-status-critical)]/10 hover:-translate-y-px active:translate-y-0 disabled:opacity-50 disabled:hover:translate-y-0",
};

const sizeClasses: Record<Size, string> = {
  sm: "text-sm px-3 py-1.5",
  md: "text-sm px-4 py-2.5",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = "primary", size = "md", isLoading, className = "", children, disabled, ...props }, ref) => {
    return (
      <button
        ref={ref}
        disabled={disabled || isLoading}
        className={`inline-flex items-center justify-center gap-2 rounded-[var(--radius-sm)] font-medium transition-[background-color,border-color,color,transform,box-shadow] duration-[var(--duration-fast)] ease-[var(--ease-standard)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-brand-strong)] motion-reduce:hover:translate-y-0 ${variantClasses[variant]} ${sizeClasses[size]} ${className}`}
        {...props}
      >
        {isLoading && (
          <span
            aria-hidden
            className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent motion-reduce:animate-none"
          />
        )}
        {children}
      </button>
    );
  }
);
Button.displayName = "Button";
