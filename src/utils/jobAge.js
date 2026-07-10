/**
 * Calculate job age and freshness level from Greenhouse updated_at timestamp
 */

export function calculateJobAge(updatedAt) {
  if (!updatedAt) {
    return {
      jobAgeHours: Infinity,
      jobAgeText: 'Updated time unknown',
      freshnessLevel: 'OLDER'
    };
  }

  const updatedDate = new Date(updatedAt);
  const now = new Date();
  const diffMs = now - updatedDate;
  const jobAgeHours = diffMs / (1000 * 60 * 60);

  let jobAgeText;
  if (jobAgeHours < 1) {
    jobAgeText = 'Updated less than 1 hour ago';
  } else if (jobAgeHours < 24) {
    const hours = Math.round(jobAgeHours);
    jobAgeText = `Updated ${hours} hour${hours === 1 ? '' : 's'} ago`;
  } else if (jobAgeHours < 48) {
    jobAgeText = 'Updated 1 day ago';
  } else {
    const days = Math.round(jobAgeHours / 24);
    jobAgeText = `Updated ${days} days ago`;
  }

  let freshnessLevel;
  if (jobAgeHours <= 3) {
    freshnessLevel = 'VERY_FRESH';
  } else if (jobAgeHours <= 12) {
    freshnessLevel = 'FRESH';
  } else if (jobAgeHours <= 24) {
    freshnessLevel = 'TODAY';
  } else if (jobAgeHours <= 72) {
    freshnessLevel = 'RECENT';
  } else {
    freshnessLevel = 'OLDER';
  }

  return {
    jobAgeHours,
    jobAgeText,
    freshnessLevel
  };
}
