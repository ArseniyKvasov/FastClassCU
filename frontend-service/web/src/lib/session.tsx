import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "./apiClient";

interface SessionState {
  authenticated: boolean;
  accessLevel: "guest" | "full" | null;
  userId: string | null;
}

interface SessionContextValue extends SessionState {
  loading: boolean;
  loginAsGuest: () => Promise<void>;
  logout: () => Promise<void>;
  loginWithProvider: (providerKey: string) => void;
  refresh: () => Promise<void>;
}

interface SessionOut {
  authenticated: boolean;
  access_level: "guest" | "full" | null;
  user_id: string | null;
}

const SessionContext = createContext<SessionContextValue | null>(null);
const EMPTY_SESSION: SessionState = { authenticated: false, accessLevel: null, userId: null };

function toState(out: SessionOut): SessionState {
  return { authenticated: out.authenticated, accessLevel: out.access_level, userId: out.user_id };
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<SessionState>(EMPTY_SESSION);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    const out = await api.get<SessionOut>("/auth/session");
    setSession(toState(out));
  }, []);

  useEffect(() => {
    refresh().finally(() => setLoading(false));
  }, [refresh]);

  const loginAsGuest = useCallback(async () => {
    const out = await api.post<SessionOut>("/auth/guest");
    setSession(toState(out));
  }, []);

  const logout = useCallback(async () => {
    await api.post("/auth/logout");
    setSession(EMPTY_SESSION);
  }, []);

  const loginWithProvider = useCallback((providerKey: string) => {
    window.location.href = `/auth/${providerKey}/login`;
  }, []);

  const value = useMemo(
    () => ({ ...session, loading, loginAsGuest, logout, loginWithProvider, refresh }),
    [session, loading, loginAsGuest, logout, loginWithProvider, refresh],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionContextValue {
  const ctx = useContext(SessionContext);
  if (!ctx) {
    throw new Error("useSession must be used within a SessionProvider");
  }
  return ctx;
}
