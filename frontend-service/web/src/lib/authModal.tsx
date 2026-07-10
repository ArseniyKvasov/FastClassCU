import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

interface AuthModalOptions {
  message?: string;
}

interface AuthModalContextValue {
  isOpen: boolean;
  message: string | undefined;
  openAuthModal: (options?: AuthModalOptions) => void;
  closeAuthModal: () => void;
}

const AuthModalContext = createContext<AuthModalContextValue | null>(null);

export function AuthModalProvider({ children }: { children: ReactNode }) {
  const [isOpen, setOpen] = useState(false);
  const [message, setMessage] = useState<string | undefined>(undefined);

  const openAuthModal = useCallback((options?: AuthModalOptions) => {
    setMessage(options?.message);
    setOpen(true);
  }, []);

  const closeAuthModal = useCallback(() => setOpen(false), []);

  const value = useMemo(
    () => ({ isOpen, message, openAuthModal, closeAuthModal }),
    [isOpen, message, openAuthModal, closeAuthModal],
  );

  return <AuthModalContext.Provider value={value}>{children}</AuthModalContext.Provider>;
}

export function useAuthModal(): AuthModalContextValue {
  const ctx = useContext(AuthModalContext);
  if (!ctx) {
    throw new Error("useAuthModal must be used within an AuthModalProvider");
  }
  return ctx;
}
