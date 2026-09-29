import { createContext, useCallback, useEffect, useMemo, useState } from 'react';
import * as authApi from '../services/authApi';

/**
 * Auth state for the whole app, derived from GET /api/auth/me.
 * The session itself is the server's HttpOnly cookies; this context holds only
 * the public user ({ id, email, name }) in memory — never tokens, never localStorage.
 *
 * status: 'loading' | 'authenticated' | 'unauthenticated' | 'unavailable'
 * ('unavailable' = the auth service could not be reached; the app keeps working signed out).
 */
export const AuthContext = createContext(null);

// Supabase email links append tokens/errors to the URL fragment. The backend owns the
// session, so drop them from the address bar and history instead of leaving them visible.
function stripAuthFragment() {
  const hash = window.location.hash || '';
  if (/(^|[#&])(access_token|refresh_token|error_description|error_code)=/.test(hash)) {
    window.history.replaceState(window.history.state, '', window.location.pathname + window.location.search);
  }
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [status, setStatus] = useState('loading');
  const [error, setError] = useState(null);

  const applySession = useCallback(data => {
    const signedIn = Boolean(data?.authenticated && data.user);
    setUser(signedIn ? data.user : null);
    setStatus(signedIn ? 'authenticated' : 'unauthenticated');
    return signedIn;
  }, []);

  /** Re-reads the session from the server (GET /api/auth/me). */
  const refresh = useCallback(async () => {
    try {
      const data = await authApi.getCurrentUser();
      setError(null);
      return applySession(data);
    } catch (err) {
      setUser(null);
      setStatus('unavailable');
      setError(err);
      return false;
    }
  }, [applySession]);

  useEffect(() => {
    stripAuthFragment();
    refresh();
  }, [refresh]);

  const login = useCallback(async credentials => {
    setError(null);
    try {
      const data = await authApi.login(credentials);
      applySession(data);
      return data;
    } catch (err) {
      setError(err);
      throw err;
    }
  }, [applySession]);

  /** Resolves to the signup response; check `emailVerificationRequired`. */
  const signup = useCallback(async details => {
    setError(null);
    try {
      const data = await authApi.signup(details);
      if (data.authenticated) applySession(data);
      return data;
    } catch (err) {
      setError(err);
      throw err;
    }
  }, [applySession]);

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } finally {
      // Server clears the cookies; locally we are signed out either way.
      setUser(null);
      setStatus('unauthenticated');
      setError(null);
    }
  }, []);

  const value = useMemo(() => ({
    user,
    status,
    loading: status === 'loading',
    isAuthenticated: status === 'authenticated',
    error,
    login,
    signup,
    logout,
    refresh
  }), [user, status, error, login, signup, logout, refresh]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
