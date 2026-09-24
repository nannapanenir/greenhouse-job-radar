/**
 * Greenhouse API Service
 * Fetches jobs from Greenhouse job boards
 */

import { calculateJobAge } from '../utils/jobAge';
import { cleanHtmlContent } from '../utils/htmlCleaner';
import { matchesLocation } from '../utils/jobFilters';
import { LOCATION_KEYWORDS } from './roleProfileService';

const NO_LOCATION = 'Location Not Provided';

/**
 * Fetch jobs from a single Greenhouse board
 */
async function fetchCompanyJobs(company) {
  const url = `https://boards-api.greenhouse.io/v1/boards/${company.token}/jobs?content=true`;

  const response = await fetch(url);

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }

  const data = await response.json();
  return {
    company,
    jobs: data.jobs || []
  };
}

/**
 * Normalize a Greenhouse job into our standard format
 */
function normalizeJob(rawJob, company) {
  const { jobAgeHours, jobAgeText, freshnessLevel } = calculateJobAge(rawJob.updated_at);

  return {
    id: rawJob.id,
    companyName: company.name,
    companyToken: company.token,
    title: rawJob.title || 'Untitled Position',
    location: rawJob.location?.name || rawJob.location || NO_LOCATION,
    updatedAt: rawJob.updated_at,
    absoluteUrl: rawJob.absolute_url,
    content: rawJob.content,
    cleanContent: cleanHtmlContent(rawJob.content),
    jobAgeHours,
    jobAgeText,
    freshnessLevel
  };
}

/**
 * Process raw jobs from a company.
 * Only the US location filter is applied here; role keyword matching happens
 * client-side (applyRoleProfile) so switching roles needs no refetch.
 * Jobs with no location are kept since they may be remote.
 */
function processCompanyJobs(company, rawJobs) {
  return rawJobs
    .map(rawJob => normalizeJob(rawJob, company))
    .filter(job => job.location === NO_LOCATION || matchesLocation(job.location, LOCATION_KEYWORDS));
}

/**
 * Fetch jobs from all enabled companies
 * @param {Array<{name: string, token: string, enabled: boolean}>} companies
 */
export async function fetchAllJobs(companies) {
  const enabledCompanies = companies.filter(c => c.enabled === true);

  const results = await Promise.allSettled(
    enabledCompanies.map(company => fetchCompanyJobs(company))
  );

  const successfulCompanies = [];
  const failedCompanies = [];
  const allJobs = [];

  for (const result of results) {
    if (result.status === 'fulfilled') {
      const { company, jobs } = result.value;
      const processedJobs = processCompanyJobs(company, jobs);

      successfulCompanies.push({
        name: company.name,
        token: company.token,
        totalJobs: jobs.length,
        usJobs: processedJobs.length
      });

      allJobs.push(...processedJobs);
    } else {
      const company = enabledCompanies[results.indexOf(result)];
      failedCompanies.push({
        name: company.name,
        token: company.token,
        error: result.reason?.message || 'Unknown error'
      });
    }
  }

  // Remove duplicates based on absoluteUrl
  const seenUrls = new Set();
  const uniqueJobs = [];

  for (const job of allJobs) {
    const key = job.absoluteUrl || `${job.companyToken}-${job.id}`;
    if (!seenUrls.has(key)) {
      seenUrls.add(key);
      uniqueJobs.push(job);
    }
  }

  // Sort by updatedAt descending (newest first)
  uniqueJobs.sort((a, b) => new Date(b.updatedAt) - new Date(a.updatedAt));

  return {
    jobs: uniqueJobs,
    successfulCompanies,
    failedCompanies,
    totalCompaniesSearched: enabledCompanies.length,
    totalJobs: uniqueJobs.length
  };
}

/**
 * Get companies configuration for display
 * @param {Array<{name: string, token: string, enabled: boolean}>} companies
 */
export function getCompaniesConfig(companies = []) {
  return companies;
}
