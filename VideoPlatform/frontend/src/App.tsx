import { useState } from 'react';
import { NavLink, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { useAuth } from './auth-context';
import { applyTheme, getTheme, Theme } from './theme';
import { isConfigured } from './config';
import Login from './pages/Login';
import Library from './pages/Library';
import Player from './pages/Player';
import Analytics from './pages/Analytics';
import Settings from './pages/Settings';

function RequireAuth({ children }: { children: JSX.Element }) {
  const { loading, authed } = useAuth();
  const location = useLocation();
  if (loading) return <div className="center muted">Carregando…</div>;
  if (!authed) return <Navigate to="/login" state={{ from: location }} replace />;
  return children;
}

function Shell({ children }: { children: JSX.Element }) {
  const { email, signOut } = useAuth();
  const [theme, setTheme] = useState<Theme>(getTheme());
  function toggleTheme() {
    const next: Theme = theme === 'dark' ? 'light' : 'dark';
    applyTheme(next);
    setTheme(next);
  }
  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">🎬 VideoPlatform</div>
        <nav className="menu">
          <NavLink to="/biblioteca">Biblioteca</NavLink>
          <NavLink to="/player">Player</NavLink>
          <NavLink to="/analytics">Analytics</NavLink>
          <NavLink to="/config">Config</NavLink>
        </nav>
        <div className="user">
          <button
            className="theme-toggle"
            onClick={toggleTheme}
            title={theme === 'dark' ? 'Mudar para tema claro' : 'Mudar para tema escuro'}
          >
            {theme === 'dark' ? '☀️' : '🌙'}
          </button>
          <span className="muted">{email}</span>
          <button className="link" onClick={signOut}>
            Sair
          </button>
        </div>
      </header>
      <main className="content">{children}</main>
    </div>
  );
}

export default function App() {
  if (!isConfigured()) {
    return (
      <div className="center">
        <div className="card">
          <h2>Configuração ausente</h2>
          <p className="muted">
            Defina <code>userPoolId</code> e <code>userPoolClientId</code> em{' '}
            <code>/config.js</code> (produção) ou no <code>.env</code> (dev) após o{' '}
            <code>cdk deploy</code>.
          </p>
        </div>
      </div>
    );
  }

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/biblioteca"
        element={
          <RequireAuth>
            <Shell>
              <Library />
            </Shell>
          </RequireAuth>
        }
      />
      <Route
        path="/player"
        element={
          <RequireAuth>
            <Shell>
              <Player />
            </Shell>
          </RequireAuth>
        }
      />
      <Route
        path="/analytics"
        element={
          <RequireAuth>
            <Shell>
              <Analytics />
            </Shell>
          </RequireAuth>
        }
      />
      <Route
        path="/config"
        element={
          <RequireAuth>
            <Shell>
              <Settings />
            </Shell>
          </RequireAuth>
        }
      />
      <Route path="*" element={<Navigate to="/biblioteca" replace />} />
    </Routes>
  );
}
