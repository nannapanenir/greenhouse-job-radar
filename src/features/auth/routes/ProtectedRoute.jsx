import { useAuth } from '../hooks/useAuth';

/**
 * Renders children only for a signed-in user. Prepared for later: no existing
 * page is wrapped yet, so the current (public) experience is unchanged.
 *
 *   <ProtectedRoute fallback={<SignInPage />}>...</ProtectedRoute>
 *
 * Placeholder visuals only; the final design replaces `loadingFallback`/`fallback`.
 */
export default function ProtectedRoute({ children, fallback = null, loadingFallback = null }) {
  const { loading, isAuthenticated } = useAuth();

  if (loading) {
    return loadingFallback ?? <p className="p-6 text-sm text-slate-500" role="status">Checking your session…</p>;
  }
  if (!isAuthenticated) {
    return fallback ?? <p className="p-6 text-sm text-slate-600">Please sign in to view this page.</p>;
  }
  return children;
}
