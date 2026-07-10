import { useEffect } from "react";
import { createPortal } from "react-dom";

interface PreviewOverlayProps {
  image: { src: string; alt: string } | null;
  onClose: () => void;
}

/** Ported verbatim from core/templates/core/pages/landing/_preview_overlay.html */
export function PreviewOverlay({ image, onClose }: PreviewOverlayProps) {
  useEffect(() => {
    if (!image) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    document.body.classList.add("lesson-preview-open");
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.classList.remove("lesson-preview-open");
    };
  }, [image, onClose]);

  return createPortal(
    <div
      className={`lesson-preview-overlay ${image ? "" : "d-none"}`}
      aria-hidden={image ? "false" : "true"}
      onClick={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <button type="button" className="lesson-preview-close" onClick={onClose} aria-label="Закрыть просмотр">
        <i className="bi bi-x-lg"></i>
      </button>
      <img src={image?.src ?? ""} alt={image?.alt ?? ""} />
    </div>,
    document.body,
  );
}
