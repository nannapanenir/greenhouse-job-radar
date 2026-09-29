import { useState } from 'react';
import { useAuth } from '../hooks/useAuth';
import ProtectedRoute from '../routes/ProtectedRoute';

/**
 * TEMPORARY test harness for validating auth on a Vercel Preview (/auth-dev).
 * Not linked from the navigation and intentionally unstyled: the premium
 * Login/Signup design replaces this page. Delete it when that lands.
 */
export default function AuthDevPage() {
  const { user, status, error, login, signup, logout, refresh } = useAuth();
  const [form, setForm] = useState({ name: '', email: '', password: '' });
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);

  const update = field => event => setForm(f => ({ ...f, [field]: event.target.value }));

  const run = action => async event => {
    event?.preventDefault();
    setBusy(true);
    setMessage('');
    try {
      setMessage(await action());
    } catch (err) {
      setMessage(`${err.message} (${err.code || 'error'})`);
    } finally {
      setBusy(false);
    }
  };

  const doSignup = run(async () => {
    const data = await signup(form);
    return data.emailVerificationRequired
      ? 'Account created. Check your email to verify it, then sign in.'
      : 'Account created and signed in.';
  });
  const doLogin = run(async () => {
    await login({ email: form.email, password: form.password });
    return 'Signed in.';
  });
  const doLogout = run(async () => {
    await logout();
    return 'Signed out.';
  });
  const doRefresh = run(async () => ((await refresh()) ? 'Session is valid.' : 'Not signed in.'));

  const input = 'block w-full border border-slate-300 rounded px-2 py-1 text-sm';
  const button = 'border border-slate-400 rounded px-3 py-1 text-sm disabled:opacity-50';

  return (
    <main className="max-w-md mx-auto p-6 space-y-4 text-sm" data-testid="auth-dev">
      <h2 className="text-base font-semibold">Auth test page (temporary)</h2>
      <p data-testid="auth-status">
        Status: <strong>{status}</strong>
        {user && <> — {user.name || '(no name)'} &lt;{user.email}&gt;</>}
      </p>
      {status === 'unavailable' && error && <p className="text-red-700">{error.message}</p>}

      <form className="space-y-2" onSubmit={doLogin}>
        <label className="block">Name (sign up only)<input className={input} value={form.name} onChange={update('name')} autoComplete="name" /></label>
        <label className="block">Email<input className={input} type="email" value={form.email} onChange={update('email')} autoComplete="email" /></label>
        <label className="block">Password<input className={input} type="password" value={form.password} onChange={update('password')} autoComplete="current-password" /></label>
        <div className="flex flex-wrap gap-2">
          <button type="submit" className={button} disabled={busy}>Log in</button>
          <button type="button" className={button} disabled={busy} onClick={doSignup}>Sign up</button>
          <button type="button" className={button} disabled={busy} onClick={doLogout}>Log out</button>
          <button type="button" className={button} disabled={busy} onClick={doRefresh}>Check session</button>
        </div>
      </form>
      {message && <p data-testid="auth-message">{message}</p>}

      <section className="border-t pt-4">
        <h3 className="font-medium">ProtectedRoute preview</h3>
        <ProtectedRoute>
          <p data-testid="protected-content">Protected content visible to {user?.email}.</p>
        </ProtectedRoute>
      </section>
    </main>
  );
}
