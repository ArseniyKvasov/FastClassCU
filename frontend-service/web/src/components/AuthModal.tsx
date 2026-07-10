import { useEffect, useRef, useState } from "react";
import { Modal } from "bootstrap";
import { api } from "../lib/apiClient";
import { useAuthModal } from "../lib/authModal";
import { useSession } from "../lib/session";
import appleTouchIcon from "../legacy/favicon/apple-touch-icon.png";
import "./AuthModal.css";

interface ProviderOut {
  key: string;
  display_name: string;
}

/**
 * Ported verbatim (DOM structure + CSS + behavior) from
 * authapp/static/auth/socialAuth.js's _createModal()/_ensureStyles(),
 * driven by the real Bootstrap Modal component so show/hide, backdrop and
 * focus-trap behavior match the monolith exactly.
 */
export function AuthModal() {
  const { isOpen, message, closeAuthModal } = useAuthModal();
  const { loginWithProvider } = useSession();
  const elRef = useRef<HTMLDivElement>(null);
  const modalRef = useRef<Modal | null>(null);
  const [providers, setProviders] = useState<ProviderOut[] | null>(null);
  const [hasError, setHasError] = useState(false);
  const [pendingProvider, setPendingProvider] = useState<string | null>(null);

  useEffect(() => {
    const el = elRef.current;
    if (!el) return;
    const modal = new Modal(el);
    modalRef.current = modal;

    const onHidden = () => closeAuthModal();
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
    setHasError(false);
    setPendingProvider(null);
    api
      .get<ProviderOut[]>("/auth/providers")
      .then(setProviders)
      .catch(() => setHasError(true));
  }, [isOpen]);

  const handleProviderClick = (providerKey: string) => {
    setPendingProvider(providerKey);
    window.setTimeout(() => {
      loginWithProvider(providerKey);
    }, 120);
  };

  return (
    <div className="modal fade" tabIndex={-1} aria-hidden="true" ref={elRef}>
      <div className="modal-dialog modal-dialog-centered modal-sm">
        <div className="modal-content social-auth-modal-content">
          <div className="modal-header border-0 pb-0 pt-3 px-3 px-sm-4">
            <h5 className="modal-title social-auth-caption mb-0">Авторизация</h5>
            <button type="button" className="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>

          <div className="modal-body text-center pt-1 pb-4 px-3 px-sm-4">
            <div className="social-auth-logo-wrap mt-1 mb-2">
              <div className="social-auth-logo social-auth-logo--core" style={{ background: "transparent" }}>
                <img
                  src={appleTouchIcon}
                  alt="Favicon"
                  style={{ width: 44, height: 44, borderRadius: 13, objectFit: "contain" }}
                />
              </div>
            </div>

            <h6 className="fw-bold mt-2 mb-2 social-auth-title">{message || "Авторизуйтесь для продолжения"}</h6>
            <p className="social-auth-subtitle mb-3">Выберите удобный способ входа</p>

            <div className="d-grid gap-2">
              {providers === null && !hasError ? (
                <div className="social-auth-loading text-center py-2">
                  <span className="spinner-border spinner-border-sm text-secondary" role="status" aria-hidden="true"></span>
                </div>
              ) : null}

              {hasError || providers?.length === 0 ? (
                <div className="text-center text-muted small py-2">Вход временно недоступен. Попробуйте позже.</div>
              ) : null}

              {providers?.map((provider) => (
                <button
                  key={provider.key}
                  type="button"
                  className={`btn w-100 d-flex align-items-center justify-content-center gap-2 social-auth-button social-auth-button--${provider.key}`}
                  data-provider={provider.key}
                  disabled={pendingProvider !== null}
                  onClick={() => handleProviderClick(provider.key)}
                >
                  {pendingProvider === provider.key ? (
                    <span
                      className="spinner-border spinner-border-sm text-secondary"
                      role="status"
                      aria-hidden="true"
                    ></span>
                  ) : null}
                  <span className="social-auth-button-label fw-semibold">Войти через {provider.display_name}</span>
                </button>
              ))}
            </div>

            <div className="mt-4 pt-2 border-top d-none">
              <button type="button" className="btn btn-sm text-muted px-3">
                <i className="bi bi-arrow-left me-1"></i>Назад
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
