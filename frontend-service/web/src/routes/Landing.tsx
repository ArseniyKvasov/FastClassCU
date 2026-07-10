import { useState } from "react";
import { useSession } from "../lib/session";
import { useAuthModal } from "../lib/authModal";
import { useToast } from "../components/Toast";
import { Hero } from "./landing/Hero";
import { Compare } from "./landing/Compare";
import { Examples } from "./landing/Examples";
import { Features } from "./landing/Features";
import { Cta } from "./landing/Cta";
import { PreviewOverlay } from "./landing/PreviewOverlay";
import "../legacy/css/landing.css";

/** Ported verbatim from core/templates/core/pages/landing.html */
export function Landing() {
  const { loginAsGuest } = useSession();
  const { openAuthModal } = useAuthModal();
  const { show } = useToast();
  const [guestPending, setGuestPending] = useState(false);
  const [preview, setPreview] = useState<{ src: string; alt: string } | null>(null);

  const handleGuestStart = async () => {
    setGuestPending(true);
    try {
      await loginAsGuest();
    } catch {
      show("Не удалось открыть класс. Попробуйте снова.", "error");
    } finally {
      setGuestPending(false);
    }
  };

  return (
    <div className="fc-page">
      <Hero
        onGuestStart={handleGuestStart}
        guestPending={guestPending}
        onLoginClick={() => openAuthModal({ message: "Войдите, чтобы продолжить" })}
      />
      <Compare onPreview={(src, alt) => setPreview({ src, alt })} />
      <Examples onPreview={(src, alt) => setPreview({ src, alt })} />
      <Features />
      <Cta onGuestStart={handleGuestStart} guestPending={guestPending} />
      <PreviewOverlay image={preview} onClose={() => setPreview(null)} />
    </div>
  );
}
