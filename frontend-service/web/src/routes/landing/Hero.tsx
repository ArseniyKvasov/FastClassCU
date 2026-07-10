import { useEffect, useRef } from "react";
import heroTutor from "../../legacy/images/home/hero-tutor.png";
import heroStudent from "../../legacy/images/home/hero-student.png";

interface HeroProps {
  onGuestStart: () => void;
  guestPending: boolean;
  onLoginClick: () => void;
}

/**
 * Ported verbatim (markup + behavior) from
 * core/templates/core/pages/landing/_hero_section.html and the parallax
 * script in landing.html. Styling comes entirely from the copied
 * legacy/css/landing.css - no component-local CSS.
 */
export function Hero({ onGuestStart, guestPending, onLoginClick }: HeroProps) {
  const sectionRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const heroSection = sectionRef.current;
    if (!heroSection) return;

    const heroLiveCards = Array.from(
      heroSection.querySelectorAll<HTMLElement>(".fc-hero-live-layer [data-depth]"),
    );
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const desktopParallax = window.matchMedia("(min-width: 992px)").matches;

    if (!heroLiveCards.length || reducedMotion || !desktopParallax) return;

    let pointerX = 0;
    let pointerY = 0;
    let rafId: number | null = null;

    function animateCards() {
      const rect = heroSection!.getBoundingClientRect();
      const dx = (pointerX - rect.left) / Math.max(rect.width, 1) - 0.5;
      const dy = (pointerY - rect.top) / Math.max(rect.height, 1) - 0.5;

      heroLiveCards.forEach((card) => {
        const depth = Number(card.dataset.depth || 0.4);
        const tx = -(dx * depth * 42);
        const ty = -(dy * depth * 30);
        card.style.transform = `translate3d(${tx.toFixed(2)}px, ${ty.toFixed(2)}px, 0)`;
      });
      rafId = null;
    }

    const onPointerMove = (event: PointerEvent) => {
      pointerX = event.clientX;
      pointerY = event.clientY;
      if (!rafId) rafId = requestAnimationFrame(animateCards);
    };

    const onPointerLeave = () => {
      heroLiveCards.forEach((card) => {
        card.style.transform = "translate3d(0, 0, 0)";
      });
    };

    heroSection.addEventListener("pointermove", onPointerMove);
    heroSection.addEventListener("pointerleave", onPointerLeave);
    return () => {
      heroSection.removeEventListener("pointermove", onPointerMove);
      heroSection.removeEventListener("pointerleave", onPointerLeave);
      if (rafId) cancelAnimationFrame(rafId);
    };
  }, []);

  return (
    <section className="fc-section fc-landing-hero" ref={sectionRef}>
      <div className="fc-hero-live-layer" aria-hidden="true">
        <div className="fc-hero-orbit"></div>
        <span className="fc-hero-particle p1"></span>
        <span className="fc-hero-particle p2"></span>
        <span className="fc-hero-particle p3"></span>
        <span className="fc-hero-particle p4"></span>
        <span className="fc-hero-bubble-icon i1">
          <i className="bi bi-chat-dots-fill"></i>
        </span>
        <span className="fc-hero-bubble-icon i2">
          <i className="bi bi-people-fill"></i>
        </span>
        <span className="fc-hero-bubble-icon i3">
          <i className="bi bi-camera-video-fill"></i>
        </span>
        <span className="fc-hero-bubble-icon i4">
          <i className="bi bi-mortarboard-fill"></i>
        </span>

        <article className="fc-hero-float-card fc-hero-chat-card" data-depth="0.36">
          <div className="fc-hero-card-head">
            <span>Чат класса</span>
          </div>
          <div className="fc-hero-msg">
            <img className="fc-hero-avatar" src={heroTutor} alt="" />
            <div className="fc-hero-bubble">Привет! Готов начать урок?</div>
          </div>
          <div className="fc-hero-msg">
            <img className="fc-hero-avatar" src={heroStudent} alt="" />
            <div className="fc-hero-bubble">Да, подключаюсь к звонку!</div>
          </div>
          <div className="fc-hero-chat-input">
            <span>Напишите сообщение...</span>
            <i className="bi bi-send-fill"></i>
          </div>
        </article>

        <article className="fc-hero-float-card fc-hero-video-card" data-depth="0.6">
          <div className="fc-hero-video-bg">
            <div className="fc-hero-controls">
              <span>
                <i className="bi bi-mic-fill"></i>
              </span>
              <span>
                <i className="bi bi-camera-video-fill"></i>
              </span>
              <span>
                <i className="bi bi-display-fill"></i>
              </span>
              <span className="is-end">
                <i className="bi bi-telephone-x-fill"></i>
              </span>
            </div>
          </div>
        </article>

        <article className="fc-hero-float-card fc-hero-task-card" data-depth="0.56">
          <div className="fc-hero-card-head">Present Perfect</div>
          <div className="fc-hero-english-task">
            <div className="fc-hero-sentence">
              1. She <span className="fc-hero-gap">has visited</span> London twice.
            </div>
            <div className="fc-hero-sentence">
              2. They <span className="fc-hero-gap is-empty">____</span> their homework yet.
            </div>
            <div className="fc-hero-word-bank">
              <span>have finished</span>
              <span>did finish</span>
              <span>finishes</span>
            </div>
          </div>
        </article>

        <article className="fc-hero-float-card fc-hero-progress-card" data-depth="0.32">
          <div className="fc-hero-card-head fc-hero-progress-title">Прогресс класса</div>
          <div className="fc-hero-progress-left">
            <div className="fc-hero-ring">78%</div>
          </div>
          <div className="fc-hero-progress-right">
            <div className="fc-hero-bars">
              <div className="fc-hero-bar-item">
                <span className="fc-hero-bar" style={{ "--h": "82%" } as React.CSSProperties}></span>
                <em>А</em>
              </div>
              <div className="fc-hero-bar-item">
                <span className="fc-hero-bar" style={{ "--h": "92%" } as React.CSSProperties}></span>
                <em>М</em>
              </div>
              <div className="fc-hero-bar-item">
                <span className="fc-hero-bar" style={{ "--h": "68%" } as React.CSSProperties}></span>
                <em>К</em>
              </div>
              <div className="fc-hero-bar-item">
                <span className="fc-hero-bar" style={{ "--h": "74%" } as React.CSSProperties}></span>
                <em>Л</em>
              </div>
              <div className="fc-hero-bar-item">
                <span className="fc-hero-bar" style={{ "--h": "54%" } as React.CSSProperties}></span>
                <em>Т</em>
              </div>
            </div>
          </div>
        </article>
      </div>

      <div className="fc-landing-hero-copy">
        <h1 className="fc-landing-hero-title">Всё для ваших уроков на одной платформе</h1>
        <p className="fc-landing-hero-text">Готовые задания, связь и виртуальная доска в одном классе</p>
        <div className="fc-landing-hero-actions">
          <button type="button" className="fc-primary-btn" disabled={guestPending} onClick={onGuestStart}>
            <i className="bi bi-lightning-charge-fill"></i>
            Перейти к уроку
          </button>
          <button type="button" className="fc-secondary-btn" onClick={onLoginClick}>
            Войти
          </button>
        </div>
        <div className="fc-hero-mobile-features" aria-hidden="true">
          <div className="fc-hero-mobile-feature is-video">
            <i className="bi bi-camera-video-fill"></i>
            <span>Видеосвязь</span>
          </div>
          <div className="fc-hero-mobile-feature is-chat">
            <i className="bi bi-chat-dots-fill"></i>
            <span>Чат</span>
          </div>
          <div className="fc-hero-mobile-feature is-board">
            <i className="bi bi-easel2-fill"></i>
            <span>Доска</span>
          </div>
          <div className="fc-hero-mobile-feature is-task">
            <i className="bi bi-ui-checks-grid"></i>
            <span>Задания</span>
          </div>
          <div className="fc-hero-mobile-feature is-progress">
            <i className="bi bi-graph-up-arrow"></i>
            <span>Прогресс</span>
          </div>
        </div>
      </div>
    </section>
  );
}
