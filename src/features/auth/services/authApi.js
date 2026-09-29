/**
 * Job Radar auth API client. Talks ONLY to our FastAPI backend (/api/auth/*);
 * the backend talks to Supabase. Tokens live in HttpOnly cookies that the
 * browser sends automatically (same origin): this module never sees them and
 * nothing auth-related is stored in localStorage.
 */

const AUTH_BASE = '/api/auth';
const GENERIC_ERROR = 'Something went wrong. Please try again.';

export class AuthApiError extends Error {
  constructor(message, { status = 0, code = 'request_failed' } = {}) {
    super(message);
    this.name = 'AuthApiError';
    this.status = status;
    this.code = code;
  }
}

function errorMessage(data) {
  if (typeof data?.detail === 'string') return data.detail;
  // FastAPI request validation (422): [{ msg, loc, ... }]
  if (Array.isArray(data?.detail) && data.detail[0]?.msg) {
    return String(data.detail[0].msg).replace(/^Value error, /, '');
  }
  return GENERIC_ERROR;
}

async function request(path, { method = 'GET', body } = {}) {
  let response;
  try {
    response = await fetch(`${AUTH_BASE}${path}`, {
      method,
      credentials: 'same-origin',
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined
    });
  } catch {
    throw new AuthApiError('Could not reach the server. Check your connection and try again.', {
      code: 'network_error'
    });
  }
  let data = null;
  try {
    data = await response.json();
  } catch {
    data = null;
  }
  if (!response.ok) {
    const code = data?.code || (response.status === 422 ? 'validation_error' : 'request_failed');
    throw new AuthApiError(errorMessage(data), { status: response.status, code });
  }
  return data;
}

/** { authenticated: boolean, user: { id, email, name } | null } */
export const getCurrentUser = () => request('/me');

/** { authenticated: true, user } — session cookies are set by the server. */
export const login = ({ email, password }) =>
  request('/login', { method: 'POST', body: { email, password } });

/** { success, emailVerificationRequired, authenticated, user } */
export const signup = ({ name, email, password }) =>
  request('/signup', { method: 'POST', body: { name, email, password } });

export const logout = () => request('/logout', { method: 'POST' });

/** Renews the session from the refresh cookie: { authenticated: true, user } or 401 session_expired. */
export const refreshSession = () => request('/refresh', { method: 'POST' });

/**
 * fetch() for future protected APIs: on 401 session_expired it refreshes the
 * session once and retries. Not used by existing (still public) endpoints yet.
 */
export async function authFetch(input, init = {}) {
  const options = { credentials: 'same-origin', ...init };
  const response = await fetch(input, options);
  if (response.status !== 401) return response;
  const data = await response.clone().json().catch(() => null);
  if (data?.code !== 'session_expired') return response;
  try {
    await refreshSession();
  } catch {
    return response;
  }
  return fetch(input, options);
}
