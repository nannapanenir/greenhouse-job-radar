/**
 * Agent Jobs Service
 * Reads the combined Greenhouse/Lever/Ashby output written by the Python agent
 * (public/data/jobs.json) and maps it to the job shape the existing UI uses.
 *
 * Opt-in while the agent is being verified: add ?data=agent to the URL.
 * Without it, the app keeps using the live Greenhouse flow (greenhouseService).
 */

import { calculateJobAge } from '../utils/jobAge';

export const AGENT_JOBS_URL = '/data/jobs.json';
const NO_LOCATION = 'Location Not Provided';

export const SOURCE_LABELS = {
  greenhouse: 'Greenhouse',
  lever: 'Lever',
  ashby: 'Ashby'
};

export function isAgentDataEnabled() {
  try {
    return new URLSearchParams(window.location.search).get('data') === 'agent';
  } catch {
    return false;
  }
}

/**
 * Common Job (agent output) -> legacy UI job.
 * absoluteUrl must stay the exact apply URL: job statuses in localStorage are
 * keyed by it, so Greenhouse statuses carry over unchanged.
 */
export function toUiJob(job) {
  // Lever/Ashby only expose a posted time; use it for freshness when there is no update time.
  const timestamp = job.updatedAt ?? job.postedAt ?? undefined;
  const { jobAgeHours, jobAgeText, freshnessLevel } = calculateJobAge(timestamp);

  return {
    id: job.sourceJobId,
    globalId: job.id,
    source: job.source,
    companyName: job.company,
    companyToken: job.companyKey,
    title: job.title || 'Untitled Position',
    location: job.location || NO_LOCATION,
    updatedAt: timestamp,
    postedAt: job.postedAt ?? undefined,
    absoluteUrl: job.applyUrl || job.sourceUrl,
    sourceUrl: job.sourceUrl,
    cleanContent: job.description || '',
    matchedKeywords: job.matchedKeywords || [],
    metadata: job.metadata || {},
    jobAgeHours,
    jobAgeText,
    freshnessLevel
  };
}

/**
 * Agent output -> the same result shape as greenhouseService.fetchAllJobs,
 * so App.jsx and the summary/failed-company panels work unchanged.
 */
export function toFetchResult(data) {
  const companies = Array.isArray(data?.companies) ? data.companies : [];
  const jobs = (Array.isArray(data?.jobs) ? data.jobs : []).map(toUiJob);

  return {
    jobs,
    successfulCompanies: companies
      .filter(c => c.status === 'ok')
      .map(c => ({
        name: c.name,
        token: `${c.source}:${c.key}`,
        source: c.source,
        totalJobs: c.jobsFetched,
        usJobs: c.jobsKept
      })),
    failedCompanies: companies
      .filter(c => c.status !== 'ok')
      .map(c => ({
        name: `${c.name} (${SOURCE_LABELS[c.source] || c.source})`,
        token: `${c.source}:${c.key}`,
        source: c.source,
        error: c.error || 'Unknown error'
      })),
    totalCompaniesSearched: data?.statistics?.companiesSearched ?? companies.length,
    totalJobs: jobs.length,
    generatedAt: data?.generatedAt ? new Date(data.generatedAt) : null
  };
}

export async function fetchAgentJobs() {
  const response = await fetch(AGENT_JOBS_URL, { cache: 'no-store' });
  if (!response.ok) {
    throw new Error(`Agent jobs not available (HTTP ${response.status}). Run: python agent/main.py`);
  }
  return toFetchResult(await response.json());
}
