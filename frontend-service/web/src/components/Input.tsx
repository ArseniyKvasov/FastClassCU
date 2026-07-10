import { forwardRef, useId, type InputHTMLAttributes } from "react";
import "./Input.css";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  hint?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, hint, id, className, ...rest }, ref) => {
    const generatedId = useId();
    const inputId = id ?? generatedId;

    return (
      <div className="fc-field">
        {label ? (
          <label className="fc-field__label" htmlFor={inputId}>
            {label}
          </label>
        ) : null}
        <input
          ref={ref}
          id={inputId}
          className={["fc-input", error ? "fc-input--error" : "", className].filter(Boolean).join(" ")}
          aria-invalid={Boolean(error)}
          aria-describedby={error ? `${inputId}-error` : hint ? `${inputId}-hint` : undefined}
          {...rest}
        />
        {error ? (
          <span className="fc-field__error" id={`${inputId}-error`}>
            {error}
          </span>
        ) : hint ? (
          <span className="fc-field__hint" id={`${inputId}-hint`}>
            {hint}
          </span>
        ) : null}
      </div>
    );
  },
);

Input.displayName = "Input";
