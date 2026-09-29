/**
 * Minimal path router (no dependency): Jobs "/", Resume AI "/resume-ai",
 * Applications "/applications" (+ the temporary, unlinked "/auth-dev" auth
 * test page). Query strings (e.g. ?role=)
 * are preserved across navigation.
 */

import { useEffect, useState } from 'react';

export const ROUTES = {
  jobs: '/',
  resumeAI: '/resume-ai',
  applications: '/applications',
  authDev: '/auth-dev' // temporary auth test page, not in the navigation
};

const EVENT = 'jobradar:navigate';

function currentPath() {
  const path = window.location.pathname.replace(/\/+$/, '') || '/';
  return Object.values(ROUTES).includes(path) ? path : ROUTES.jobs;
}

export function navigate(path) {
  if (path === window.location.pathname) return;
  window.history.pushState(window.history.state, '', `${path}${window.location.search}`);
  window.dispatchEvent(new Event(EVENT));
  window.scrollTo(0, 0);
}

export function useRoute() {
  const [path, setPath] = useState(currentPath);
  useEffect(() => {
    const update = () => setPath(currentPath());
    window.addEventListener('popstate', update);
    window.addEventListener(EVENT, update);
    return () => {
      window.removeEventListener('popstate', update);
      window.removeEventListener(EVENT, update);
    };
  }, []);
  return path;
}
