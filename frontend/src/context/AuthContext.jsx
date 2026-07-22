import { createContext, useContext, useState, useCallback, useEffect } from 'react';
import api, { setUnauthorizedHandler } from '../lib/api';

const AuthContext = createContext(null);
// Non-sensitive profile cache for instant UI on reload — NOT a credential.
// The real session lives in httpOnly cookies and is verified against /auth/me/.
const USER_KEY = 'vs_user';

function loadUser() {
  try { return JSON.parse(localStorage.getItem(USER_KEY)); } catch { return null; }
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(loadUser);
  const [loading, setLoading] = useState(true);

  const persist = useCallback((u) => {
    if (u) localStorage.setItem(USER_KEY, JSON.stringify(u));
    else localStorage.removeItem(USER_KEY);
    setUser(u);
  }, []);

  // On mount, verify the cookie-backed session (and prime the csrftoken cookie).
  useEffect(() => {
    let alive = true;
    api.get('/auth/me/')
      .then(({ data }) => { if (alive) persist(data); })
      .catch(() => { if (alive) persist(null); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [persist]);

  // If a background refresh fails, the session is gone — clear local state.
  useEffect(() => {
    setUnauthorizedHandler(() => persist(null));
    return () => setUnauthorizedHandler(null);
  }, [persist]);

  const login = useCallback(async (email, password) => {
    // Backend sets the httpOnly JWT cookies; body carries only the user profile.
    const { data } = await api.post('/auth/login/', { email, password });
    persist(data.user);
    return data.user;
  }, [persist]);

  const register = useCallback(async (payload) => {
    const { data } = await api.post('/auth/register/', payload);
    return data;
  }, []);

  const requestReset = useCallback(async (email) => {
    await api.post('/auth/password-reset/', { email });
  }, []);

  const confirmReset = useCallback(async (uid, token, password) => {
    await api.post('/auth/password-reset/confirm/', { uid, token, password });
  }, []);

  const verifyEmail = useCallback(async (uid, token) => {
    const { data } = await api.post('/auth/verify-email/', { uid, token });
    return data;
  }, []);

  const resendVerification = useCallback(async (email) => {
    await api.post('/auth/resend-verification/', { email });
  }, []);

  const logout = useCallback(async () => {
    try { await api.post('/auth/logout/'); } catch { /* noop */ }
    persist(null);
  }, [persist]);

  const value = {
    user, role: user?.role, isAuthed: !!user, loading,
    login, register, requestReset, confirmReset, verifyEmail, resendVerification,
    logout, setUser: persist,
  };
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
