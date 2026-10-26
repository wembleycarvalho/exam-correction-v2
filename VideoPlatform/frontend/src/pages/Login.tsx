import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CognitoUser } from 'amazon-cognito-identity-js';
import { login, completeNewPassword } from '../auth';
import { useAuth } from '../auth-context';

export default function Login() {
  const nav = useNavigate();
  const { refresh } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [challengeUser, setChallengeUser] = useState<CognitoUser | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const r = await login(email, password);
      if (r.status === 'newPasswordRequired') {
        setChallengeUser(r.user || null);
      } else {
        await refresh();
        nav('/biblioteca');
      }
    } catch (err: any) {
      setError(err?.message || 'Falha no login');
    } finally {
      setBusy(false);
    }
  }

  async function onNewPassword(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (!challengeUser) return;
      await completeNewPassword(challengeUser, newPassword);
      await refresh();
      nav('/biblioteca');
    } catch (err: any) {
      setError(err?.message || 'Falha ao definir nova senha');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="center">
      <div className="card login">
        <h1>🎬 VideoPlatform</h1>
        {!challengeUser ? (
          <form onSubmit={onSubmit}>
            <label>E-mail</label>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            <label>Senha</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
            {error && <p className="error">{error}</p>}
            <button className="primary" disabled={busy}>
              {busy ? 'Entrando…' : 'Entrar'}
            </button>
          </form>
        ) : (
          <form onSubmit={onNewPassword}>
            <p className="muted">Primeiro acesso: defina uma nova senha.</p>
            <label>Nova senha</label>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
            />
            {error && <p className="error">{error}</p>}
            <button className="primary" disabled={busy}>
              {busy ? 'Salvando…' : 'Definir senha e entrar'}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
