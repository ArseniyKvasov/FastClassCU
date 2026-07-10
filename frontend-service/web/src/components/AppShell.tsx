import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { useSession } from "../lib/session";
import { useAuthModal } from "../lib/authModal";
import { QuotaModal } from "./modals/QuotaModal";
import { lessonsApi } from "../lib/lessons";
import "./AppShell.css";

function AccountMenu({ onOpenQuota }: { onOpenQuota: () => void }) {
  const { userId, accessLevel, logout } = useSession();
  const [open, setOpen] = useState(false);
  const [hasLessons, setHasLessons] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Mirrors home.html's `{% if has_any_lessons %}` - the entry point to
    // "free up space by deleting a lesson" is pointless to show when there's
    // nothing to delete yet.
    lessonsApi
      .listMine()
      .then((lessons) => setHasLessons(lessons.length > 0))
      .catch(() => setHasLessons(false));
  }, []);

  useEffect(() => {
    if (!open) return;
    const onClickOutside = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, [open]);

  const shortId = userId ? userId.slice(0, 8) : "";

  return (
    <div className="dropdown fc-account-menu" ref={ref}>
      <button
        type="button"
        className="app-user-badge app-user-badge-btn rounded-pill px-3 py-1"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
      >
        <i className="bi bi-person-circle me-1"></i>
        {accessLevel === "guest" ? "Гость" : "Аккаунт"}
      </button>
      {open ? (
        <ul className="dropdown-menu dropdown-menu-end fc-home-account-dropdown show" role="menu">
          <li className="fc-dropdown-user-info">
            <span className="fc-dropdown-username">{accessLevel === "guest" ? "Гость" : "Аккаунт"}</span>
            <span className="fc-dropdown-email">{shortId}</span>
          </li>
          {hasLessons ? (
            <>
              <li>
                <hr className="fc-dropdown-divider" />
              </li>
              <li>
                <button
                  type="button"
                  className="fc-dropdown-item fc-dropdown-item--limits"
                  onClick={() => {
                    setOpen(false);
                    onOpenQuota();
                  }}
                  role="menuitem"
                >
                  <i className="bi bi-database fc-dropdown-item-icon"></i>
                  Лимиты памяти
                </button>
              </li>
            </>
          ) : null}
          <li>
            <hr className="fc-dropdown-divider" />
          </li>
          <li>
            <button
              type="button"
              className="fc-dropdown-item fc-dropdown-item--logout"
              onClick={() => logout()}
              role="menuitem"
            >
              <i className="bi bi-box-arrow-right fc-dropdown-item-icon"></i>
              Выйти
            </button>
          </li>
        </ul>
      ) : null}
    </div>
  );
}

/**
 * Header/footer chrome ported verbatim (markup + classes) from
 * core/templates/core/base.html's navbar and footer blocks. Any
 * authenticated user (guest or full access) gets the same account dropdown
 * home.html shows for `user.is_authenticated` - guests are real logged-in
 * sessions in this system too, not a separate UI mode.
 */
export function AppShell({ children }: { children: ReactNode }) {
  const { authenticated } = useSession();
  const { openAuthModal } = useAuthModal();
  const [isQuotaOpen, setQuotaOpen] = useState(false);

  return (
    <div className="fc-shell">
      <nav className="navbar app-navbar">
        <div className="container app-navbar-inner">
          <Link to="/" className="navbar-brand app-brand">
            <span className="app-brand-mark">
              <i className="bi bi-lightning-charge-fill"></i>
            </span>
            <span>FastClass</span>
          </Link>
          <div className="app-nav-actions">
            {authenticated ? (
              <AccountMenu onOpenQuota={() => setQuotaOpen(true)} />
            ) : (
              <button type="button" className="fc-login-btn" onClick={() => openAuthModal()}>
                <i className="bi bi-person-circle me-2"></i>Войти
              </button>
            )}
          </div>
        </div>
      </nav>

      <main className="container app-main pb-4">{children}</main>

      <footer className="text-center text-muted py-3 border-top">FastClass © 2026</footer>

      <QuotaModal isOpen={isQuotaOpen} onClose={() => setQuotaOpen(false)} />
    </div>
  );
}
