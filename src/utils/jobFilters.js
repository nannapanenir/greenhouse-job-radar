/**
 * Job filtering utilities
 * Handles role profile keyword matching, location matching, and time filtering
 */

function escapeRegExp(text) {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * Build a case-insensitive, whole-word regex for a keyword.
 * Lookarounds (instead of \b) keep boundaries correct for keywords that
 * start or end with punctuation, e.g. "C++" or "Software Engineer, Web".
 * "RAG" matches "RAG Engineer" but not "leverage".
 */
export function buildKeywordRegex(keyword) {
  const pattern = escapeRegExp(keyword.trim()).replace(/\s+/g, '\\s+');
  return new RegExp(`(?<![A-Za-z0-9])${pattern}(?![A-Za-z0-9])`, 'i');
}

function compileKeywords(keywords = []) {
  return keywords
    .filter(kw => typeof kw === 'string' && kw.trim() !== '')
    .map(keyword => ({ keyword, regex: buildKeywordRegex(keyword) }));
}

/**
 * Return the include keywords that appear in the job title
 * (or title + cleanContent when searchDescription is true)
 */
export function matchIncludeKeywords(job, includeKeywords, searchDescription = false) {
  return matchCompiled(job, compileKeywords(includeKeywords), searchDescription);
}

function matchCompiled(job, compiled, searchDescription) {
  const searchText = searchDescription
    ? `${job.title || ''}\n${job.cleanContent || ''}`
    : job.title || '';

  return compiled.filter(({ regex }) => regex.test(searchText)).map(({ keyword }) => keyword);
}

/**
 * Check if a job title contains any exclude keywords (whole word)
 */
export function matchesExcludeTitle(title, excludeTitleKeywords) {
  if (!title) return false;
  return compileKeywords(excludeTitleKeywords).some(({ regex }) => regex.test(title));
}

/**
 * Apply a role profile: drop excluded titles, keep jobs with at least one
 * include keyword match, and attach matchedKeywords to each kept job
 */
export function applyRoleProfile(jobs, profile) {
  if (!profile) return [];

  const include = compileKeywords(profile.includeKeywords);
  const exclude = compileKeywords(profile.excludeTitleKeywords);
  const searchDescription = profile.searchDescription === true;
  const result = [];

  for (const job of jobs) {
    const title = job.title || '';
    if (exclude.some(({ regex }) => regex.test(title))) continue;

    const matchedKeywords = matchCompiled(job, include, searchDescription);
    if (matchedKeywords.length === 0) continue;

    result.push({ ...job, matchedKeywords });
  }

  return result;
}

/**
 * Check if a location matches any of the allowed location keywords
 */
export function matchesLocation(location, locationKeywords) {
  if (!location) return false; // No location provided, will be filtered

  const locationLower = location.toLowerCase();

  for (const keyword of locationKeywords) {
    if (locationLower.includes(keyword.toLowerCase())) {
      return true;
    }
  }

  return false;
}

/**
 * Filter jobs based on time
 */
export function filterByTime(jobs, maxAgeHours) {
  return jobs.filter(job => job.jobAgeHours <= maxAgeHours);
}

/**
 * Filter jobs based on status
 */
export function filterByStatus(jobs, statuses, jobStatuses) {
  if (!statuses || statuses.length === 0) return jobs;

  return jobs.filter(job => {
    const status = jobStatuses[job.absoluteUrl] || 'New';
    return statuses.includes(status);
  });
}

/**
 * Search jobs by title or company name
 */
export function searchJobs(jobs, searchTerm) {
  if (!searchTerm || searchTerm.trim() === '') return jobs;

  const term = searchTerm.toLowerCase().trim();

  return jobs.filter(job => {
    const title = (job.title || '').toLowerCase();
    const companyName = (job.companyName || '').toLowerCase();
    return title.includes(term) || companyName.includes(term);
  });
}

/**
 * Filter jobs by company name
 */
export function filterByCompany(jobs, companyName) {
  if (!companyName) return jobs;
  return jobs.filter(job => job.companyName === companyName);
}

/**
 * Filter jobs by matched keyword
 */
export function filterByMatchedKeyword(jobs, keyword) {
  if (!keyword) return jobs;
  return jobs.filter(job =>
    job.matchedKeywords && job.matchedKeywords.includes(keyword)
  );
}

/**
 * Sort jobs based on sort option
 */
export function sortJobs(jobs, sortBy) {
  const sorted = [...jobs];

  switch (sortBy) {
    case 'newest':
      return sorted.sort((a, b) => new Date(b.updatedAt) - new Date(a.updatedAt));
    case 'oldest':
      return sorted.sort((a, b) => new Date(a.updatedAt) - new Date(b.updatedAt));
    case 'company':
      return sorted.sort((a, b) =>
        (a.companyName || '').localeCompare(b.companyName || '')
      );
    case 'title':
      return sorted.sort((a, b) =>
        (a.title || '').localeCompare(b.title || '')
      );
    default:
      return sorted.sort((a, b) => new Date(b.updatedAt) - new Date(a.updatedAt));
  }
}

/**
 * Get unique companies from jobs
 */
export function getUniqueCompanies(jobs) {
  const companies = new Set();
  jobs.forEach(job => companies.add(job.companyName));
  return Array.from(companies).sort();
}

/**
 * Get unique matched keywords from jobs
 */
export function getUniqueMatchedKeywords(jobs) {
  const keywords = new Set();
  jobs.forEach(job => {
    if (job.matchedKeywords) {
      job.matchedKeywords.forEach(kw => keywords.add(kw));
    }
  });
  return Array.from(keywords).sort();
}
