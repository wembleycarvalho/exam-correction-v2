import { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { getSession, getEmail, signOut as doSignOut } from './auth';

interface AuthState {
  loading: boolean;
  authed: boolean;
  email: string | null;
  refresh: () => Promise<void>;
  signOut: () => void;
}

const AuthContext = createContext<AuthState>({
  loading: true,
  authed: false,
  email: null,
  refresh: async () => {},
  signOut: () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [loading, setLoading] = useState(true);
  const [authed, setAuthed] = useState(false);
  const [email, setEmail] = useState<string | null>(null);

  async function refresh() {
    const session = await getSession();
    setAuthed(Boolean(session));
    setEmail(session ? await getEmail() : null);
    setLoading(false);
  }

  useEffect(() => {
    refresh();
  }, []);

  function signOut() {
    doSignOut();
    setAuthed(false);
    setEmail(null);
  }

  return (
    <AuthContext.Provider value={{ loading, authed, email, refresh, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
