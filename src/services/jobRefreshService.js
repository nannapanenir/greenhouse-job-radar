/**
 * Job refresh: ONE request to the Python API, which fetches every provider
 * (Greenhouse, Lever, Ashby) server-side with bounded concurrency and returns
 * Common Jobs. The browser never calls provider APIs.
 */

import { toFetchResult } from './agentJobsService';

export const JOB_REFRESH_URL = '/api/jobs/refresh';

export async function refreshJobs() {
  let response;
  try {
    response = await fetch(JOB_REFRESH_URL, { method: 'POST' });
  } catch {
    throw new Error('Could not reach the Job Radar API. Check your connection and try again.');
  }
  let data = null;
  try {
    data = await response.json();
  } catch {
    // non-JSON (e.g. platform error page)
  }
  if (!response.ok) {
    const error = new Error((data && typeof data.detail === 'string' && data.detail) || `Job refresh failed (HTTP ${response.status}).`);
    error.refresh = data?.refresh || null;
    throw error;
  }
  return { ...toFetchResult(data), refresh: data.refresh || null };
}
