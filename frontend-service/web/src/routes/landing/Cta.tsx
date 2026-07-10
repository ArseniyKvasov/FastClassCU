interface CtaProps {
  onGuestStart: () => void;
  guestPending: boolean;
}

/** Ported verbatim from core/templates/core/pages/landing/_cta_section.html */
export function Cta({ onGuestStart, guestPending }: CtaProps) {
  return (
    <section className="fc-section pt-2 pb-5">
      <div className="fc-card fc-cta">
        <div className="row g-4 align-items-center">
          <div className="col-lg-7">
            <h2 className="fc-cta-title">Начни урок прямо сейчас</h2>
          </div>
          <div className="col-lg-5 text-lg-end">
            <button type="button" className="fc-primary-btn" disabled={guestPending} onClick={onGuestStart}>
              <i className="bi bi-lightning-charge-fill"></i>
              Перейти к уроку
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
