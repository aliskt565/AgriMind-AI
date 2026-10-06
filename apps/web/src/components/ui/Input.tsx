import { InputHTMLAttributes, SelectHTMLAttributes, forwardRef } from "react";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
}

const fieldBase =
  "rounded-[var(--radius-sm)] border bg-[var(--color-surface-raised)] px-3 py-2 text-sm text-[var(--color-text-primary)] outline-none transition-[border-color,box-shadow] duration-[var(--duration-fast)] ease-[var(--ease-standard)] focus:border-[var(--color-brand-strong)] focus:shadow-[0_0_0_3px_var(--color-brand-soft)]";

export const Input = forwardRef<HTMLInputElement, InputProps>(({ label, error, id, className = "", ...props }, ref) => {
  const inputId = id || label.toLowerCase().replace(/\s+/g, "-");
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={inputId} className="text-sm font-medium text-[var(--color-text-primary)]">
        {label}
      </label>
      <input
        ref={ref}
        id={inputId}
        aria-invalid={!!error}
        aria-describedby={error ? `${inputId}-error` : undefined}
        className={`${fieldBase} ${
          error ? "border-[var(--color-status-critical)] focus:shadow-[0_0_0_3px_rgba(242,104,95,0.15)]" : "border-[var(--color-border)]"
        } ${className}`}
        {...props}
      />
      {error && (
        <p id={`${inputId}-error`} className="animate-in text-xs text-[var(--color-status-critical)]">
          {error}
        </p>
      )}
    </div>
  );
});
Input.displayName = "Input";

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label: string;
  error?: string;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(({ label, error, id, className = "", children, ...props }, ref) => {
  const selectId = id || label.toLowerCase().replace(/\s+/g, "-");
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={selectId} className="text-sm font-medium text-[var(--color-text-primary)]">
        {label}
      </label>
      <select
        ref={ref}
        id={selectId}
        className={`${fieldBase} ${error ? "border-[var(--color-status-critical)]" : "border-[var(--color-border)]"} ${className}`}
        {...props}
      >
        {children}
      </select>
      {error && <p className="animate-in text-xs text-[var(--color-status-critical)]">{error}</p>}
    </div>
  );
});
Select.displayName = "Select";
