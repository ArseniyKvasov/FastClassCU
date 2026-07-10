import { useEffect, type ReactNode } from "react";
import { createPortal } from "react-dom";
import "./Modal.css";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: ReactNode;
}

export function Modal({ open, onClose, title, children }: ModalProps) {
  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  return createPortal(
    <div className="fc-modal-overlay" onMouseDown={onClose} role="presentation">
      <div
        className="fc-modal"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onMouseDown={(event) => event.stopPropagation()}
      >
        {title ? (
          <div className="fc-modal__header">
            <h2 className="fc-modal__title">{title}</h2>
            <button className="fc-modal__close" onClick={onClose} aria-label="Закрыть">
              ×
            </button>
          </div>
        ) : null}
        <div className="fc-modal__body">{children}</div>
      </div>
    </div>,
    document.body,
  );
}
