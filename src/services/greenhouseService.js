/**
 * Greenhouse API Service
 * Fetches jobs from Greenhouse job boards
 */

import companiesConfig from '../config/greenhouse-companies.json';
import jobFiltersConfig from '../config/job-filters.json';
import { calculateJobAge } from '../utils/jobAge';
import { cleanHtmlContent } from '../utils/htmlCleaner';
import { matchIncludeKeywords, matchesExcludeTitle, matchesLocation } from '../utils/jobFilters';

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

  const matchedKeywords = matchIncludeKeywords(rawJob, jobFiltersConfig.includeKeywords);

  return {
    id: rawJob.id,
    companyName: company.name,
    companyToken: company.token,
    title: rawJob.title || 'Untitled Position',
    location: rawJob.location?.name || rawJob.location || 'Location Not Provided',
    updatedAt: rawJob.updated_at,
    absoluteUrl: rawJob.absolute_url,
    content: rawJob.content,
    cleanContent: cleanHtmlContent(rawJob.content),
    matchedKeywords,
    jobAgeHours,
    jobAgeText,
    freshnessLevel
  };
}

/**
 * Process raw jobs from a company
 */
function processCompanyJobs(company, rawJobs) {
  const { includeKeywords, excludeTitleKeywords, locationKeywords } = jobFiltersConfig;

  const processedJobs = [];

  for (const rawJob of rawJobs) {
    // Normalize job
    const job = normalizeJob(rawJob, company);

    // Check if job matches include keywords
    if (job.matchedKeywords.length === 0) {
      continue;
    }

    // Check if job title matches exclude keywords
    if (matchesExcludeTitle(job.title, excludeTitleKeywords)) {
      continue;
    }

    // Check if location matches allowed keywords
    if (!matchesLocation(job.location, locationKeywords) && job.location !== 'Location Not Provided') {
      continue;
    }

    // Include jobs with "Location Not Provided" as they might be remote
    if (job.location === 'Location Not Provided') {
      // Check if content mentions US locations
      const contentLower = (job.cleanContent || '').toLowerCase();
      const mentionsUs = locationKeywords.some(kw =>
        kw.toLowerCase().includes('us') ||
        kw.toLowerCase().includes('remote')
      );
      if (!mentionsUs && !contentLower.includes('united states') && !contentLower.includes('remote us')) {
        continue;
      }
    }

    processedJobs.push(job);
  }

  return processedJobs;
}

/**
 * Fetch jobs from all enabled companies
 */
export async function fetchAllJobs() {
  const enabledCompanies = companiesConfig.filter(c => c.enabled === true);

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
        matchingJobs: processedJobs.length
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
 * Get companies configuration
 */
export function getCompaniesConfig() {
  return companiesConfig;
}

/**
 * Get job filters configuration
 */
export function getJobFiltersConfig() {
  return jobFiltersConfig;
}
