import { useContext } from 'react';
import { AuthContext } from '../context/AuthContext';

/** { user, status, loading, isAuthenticated, error, login, signup, logout, refresh } */
export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used inside <AuthProvider>');
  return context;
}
