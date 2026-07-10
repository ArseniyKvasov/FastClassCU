/*
 * These CSS imports must stay first, ahead of every component import below.
 * Vite/Rollup emits stylesheet rules in module-graph traversal order, so
 * Bootstrap's base .btn/.modal rules need to land in the bundle before any
 * component-local CSS (e.g. AuthModal.css's .social-auth-button) that
 * overrides them - otherwise equal-specificity selectors resolve by source
 * order and Bootstrap's defaults win instead.
 */
import "bootstrap/dist/css/bootstrap.min.css";
import "bootstrap-icons/font/bootstrap-icons.css";
import "./styles/globals.css";
import "./legacy/css/fonts.css";
import "./legacy/css/base.css";

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import { ThemeProvider } from "./theme/ThemeProvider";
import { SessionProvider } from "./lib/session";
import { AuthModalProvider } from "./lib/authModal";
import { ToastProvider } from "./components/Toast";
import { AuthModal } from "./components/AuthModal";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ThemeProvider>
      <ToastProvider>
        <BrowserRouter>
          <SessionProvider>
            <AuthModalProvider>
              <App />
              <AuthModal />
            </AuthModalProvider>
          </SessionProvider>
        </BrowserRouter>
      </ToastProvider>
    </ThemeProvider>
  </StrictMode>,
);
