import { useEffect, useState } from 'react';
import { LoginPage } from './pages/LoginPage';
import { Workspace } from './pages/Workspace';
import { fetchAppStatus, fetchCurrentUser, logoutUser } from './lib/api';
import type { AppStatus } from './lib/api';
import type { AuthSession } from './lib/types';

const AUTH_STORAGE_KEY = 'codecoach.auth';

export default function App() {
  const [status, setStatus] = useState<AppStatus | null>(null);
  const [session, setSession] = useState<AuthSession | null>(() => readStoredSession());
  const [authChecked, setAuthChecked] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetchAppStatus()
      .then((result) => {
        if (!cancelled) setStatus(result);
      })
      .catch(() => {
        if (!cancelled) {
          setStatus({ status: 'ok', maintenance: false, message: '' });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    if (!session?.token) {
      setAuthChecked(true);
      return () => {
        cancelled = true;
      };
    }
    fetchCurrentUser(session.token)
      .then((user) => {
        if (cancelled) return;
        const nextSession = { token: session.token, user };
        setSession(nextSession);
        storeSession(nextSession);
        setAuthChecked(true);
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof Error && err.message.startsWith('AUTH_ME_401:')) {
          clearStoredSession();
          setSession(null);
        } else {
          setSession((current) => current);
        }
        setAuthChecked(true);
      });
    return () => {
      cancelled = true;
    };
  }, [session?.token]);

  function handleAuthenticated(nextSession: AuthSession) {
    storeSession(nextSession);
    setSession(nextSession);
    setAuthChecked(true);
  }

  async function handleLogout() {
    const token = session?.token;
    clearStoredSession();
    setSession(null);
    if (token) {
      await logoutUser(token).catch(() => undefined);
    }
  }

  if (!authChecked) {
    return (
      <main className="app-stage auth-loading">
        <section className="auth-card compact">
          <span className="eyebrow dark">CodeCoach</span>
          <h1>正在确认登录状态</h1>
        </section>
      </main>
    );
  }

  if (!session) {
    return <LoginPage onAuthenticated={handleAuthenticated} />;
  }

  return (
    <Workspace
      currentUser={session.user}
      authToken={session.token}
      maintenanceMode={Boolean(status?.maintenance)}
      maintenanceMessage={status?.message ?? ''}
      statusPending={status === null}
      onLogout={handleLogout}
    />
  );
}

function readStoredSession(): AuthSession | null {
  try {
    const raw = localStorage.getItem(AUTH_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as AuthSession;
    if (!parsed.token || !parsed.user?.id) return null;
    return parsed;
  } catch {
    return null;
  }
}

function storeSession(session: AuthSession) {
  localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(session));
}

function clearStoredSession() {
  localStorage.removeItem(AUTH_STORAGE_KEY);
}
