import { forwardRef, type ButtonHTMLAttributes } from "react";
import "./Button.css";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = "primary", size = "md", loading = false, disabled, className, children, ...rest }, ref) => {
    const classes = ["fc-btn", `fc-btn--${variant}`, `fc-btn--${size}`, className].filter(Boolean).join(" ");
    return (
      <button ref={ref} className={classes} disabled={disabled || loading} aria-busy={loading} {...rest}>
        {loading ? <span className="fc-btn__spinner" aria-hidden="true" /> : null}
        <span className="fc-btn__label">{children}</span>
      </button>
    );
  },
);

Button.displayName = "Button";
