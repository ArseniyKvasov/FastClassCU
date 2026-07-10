import { useEffect, useRef, useState } from "react";
import { Modal } from "bootstrap";
import { lessonsApi, type QuotaOut } from "../../lib/lessons";
import "./QuotaModal.css";

interface QuotaModalProps {
  isOpen: boolean;
  onClose: () => void;
}

function formatBytes(bytes: number): string {
  if (!bytes) return "0 Б";
  const units = ["Б", "КБ", "МБ", "ГБ"];
  let value = bytes;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  const precision = unitIndex === 0 ? 0 : value >= 10 ? 1 : 2;
  return `${value.toFixed(precision)} ${units[unitIndex]}`;
}

export function QuotaModal({ isOpen, onClose }: QuotaModalProps) {
  const elRef = useRef<HTMLDivElement>(null);
  const modalRef = useRef<Modal | null>(null);
  const [quota, setQuota] = useState<QuotaOut | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    const el = elRef.current;
    if (!el) return;
    const modal = new Modal(el);
    modalRef.current = modal;
    const onHidden = () => onClose();
    el.addEventListener("hidden.bs.modal", onHidden);
    return () => {
      el.removeEventListener("hidden.bs.modal", onHidden);
      modal.dispose();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (isOpen) {
      modalRef.current?.show();
    } else {
      modalRef.current?.hide();
    }
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    setQuota(null);
    setError(false);
    lessonsApi
      .getQuota()
      .then(setQuota)
      .catch(() => setError(true));
  }, [isOpen]);

  const usedBytes = quota?.storage_bytes ?? 0;
  const limitBytes = quota?.limit_bytes ?? 0;
  const remainingBytes = Math.max(0, limitBytes - usedBytes);
  const usedPercent = limitBytes > 0 ? Math.min(100, (usedBytes / limitBytes) * 100) : 0;
  const tone = remainingBytes > 100 * 1024 * 1024 ? "good" : remainingBytes > 50 * 1024 * 1024 ? "warn" : "danger";

  return (
    <div className="modal fade" tabIndex={-1} aria-hidden="true" ref={elRef}>
      <div className="modal-dialog modal-dialog-centered">
        <div className="modal-content fc-quota-modal">
          <div className="modal-header fc-quota-modal-header">
            <h5 className="modal-title fc-quota-modal-title">Лимиты памяти</h5>
            <button type="button" className="btn-close" data-bs-dismiss="modal" aria-label="Закрыть"></button>
          </div>
          <div className="modal-body fc-quota-modal-body">
            {error ? (
              <p className="text-danger small mb-0">Не удалось загрузить лимиты.</p>
            ) : quota === null ? (
              <div className="text-center py-4">
                <span className="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>
              </div>
            ) : (
              <>
                <div className="fc-quota-bar-track">
                  <div className={`fc-quota-bar-fill fc-quota-bar-fill--${tone}`} style={{ width: `${usedPercent}%` }} />
                </div>
                <div className="row g-2 mt-1">
                  <div className="col-4">
                    <div className="fc-quota-summary-card">
                      <div className="fc-quota-summary-icon">
                        <i className="bi bi-pie-chart-fill"></i>
                      </div>
                      <div className="fc-quota-summary-label">Использовано</div>
                      <div className="fc-quota-summary-value">{formatBytes(usedBytes)}</div>
                    </div>
                  </div>
                  <div className="col-4">
                    <div className="fc-quota-summary-card">
                      <div className="fc-quota-summary-icon">
                        <i className="bi bi-bullseye"></i>
                      </div>
                      <div className="fc-quota-summary-label">Лимит</div>
                      <div className="fc-quota-summary-value">{formatBytes(limitBytes)}</div>
                    </div>
                  </div>
                  <div className="col-4">
                    <div className="fc-quota-summary-card">
                      <div className="fc-quota-summary-icon fc-quota-summary-icon--remaining">
                        <i className="bi bi-battery-half"></i>
                      </div>
                      <div className="fc-quota-summary-label">Осталось</div>
                      <div className={`fc-quota-summary-value fc-quota-summary-value--${tone}`}>
                        {formatBytes(remainingBytes)}
                      </div>
                    </div>
                  </div>
                </div>
                <p className="fc-quota-note">Готовые уроки можно будет загрузить заново</p>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
