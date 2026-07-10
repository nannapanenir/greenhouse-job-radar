/**
 * Job filtering utilities
 * Handles include/exclude keywords, location matching, and time filtering
 */

/**
 * Check if a job matches any of the include keywords
 * Returns array of matched keywords
 */
export function matchIncludeKeywords(job, includeKeywords) {
  const title = (job.title || '').toLowerCase();
  const content = (job.content || '').toLowerCase();
  const searchText = `${title} ${content}`;

  const matchedKeywords = [];

  for (const keyword of includeKeywords) {
    const keywordLower = keyword.toLowerCase();
    if (searchText.includes(keywordLower)) {
      matchedKeywords.push(keyword);
    }
  }

  return matchedKeywords;
}

/**
 * Check if a job title contains any exclude keywords
 */
export function matchesExcludeTitle(title, excludeTitleKeywords) {
  if (!title) return false;

  const titleLower = title.toLowerCase();

  for (const keyword of excludeTitleKeywords) {
    if (titleLower.includes(keyword.toLowerCase())) {
      return true;
    }
  }

  return false;
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
