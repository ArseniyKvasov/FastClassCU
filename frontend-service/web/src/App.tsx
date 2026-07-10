import { Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { Landing } from "./routes/Landing";
import { Home } from "./routes/Home";
import { NotFound } from "./routes/NotFound";
import { useSession } from "./lib/session";

function IndexRoute() {
  const { authenticated, loading } = useSession();
  if (loading) return null;
  return authenticated ? <Home /> : <Landing />;
}

export function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<IndexRoute />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </AppShell>
  );
}
