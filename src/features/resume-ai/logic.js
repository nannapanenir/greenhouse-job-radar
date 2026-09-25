/**
 * Client-side review logic (ported from the standalone Resume Tailor UI).
 * The server re-applies and re-validates everything at generation time;
 * these helpers only drive the live preview and scores.
 */

export const APPLIED = ['accepted', 'edited'];

// mockData.js KNOWN_SKILLS (used for "Add career information" + keyword highlight)
export const KNOWN_SKILLS = [
  'Angular', 'Angular 19', 'React', 'TypeScript', 'JavaScript', 'Node.js',
  'REST APIs', 'GraphQL', 'PrimeNG', 'NgRx', 'RxJs', 'Redux', 'HTML', 'CSS',
  'SCSS', 'CI/CD', 'Jenkins', 'Git', 'Agile', 'Scrum', 'AWS', 'Azure', 'GCP',
  'Docker', 'Kubernetes', 'Terraform', 'Microservices', 'SQL', 'MongoDB',
  'PostgreSQL', 'Java', 'Spring Boot', 'Python', 'Jest', 'Cypress', 'Webpack'
];

const escapeRegExp = s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

export function extractSkillsFromText(text) {
  const lower = (text || '').toLowerCase();
  return [...new Set(KNOWN_SKILLS.filter(skill => new RegExp(`\\b${escapeRegExp(skill)}\\b`, 'i').test(lower)))];
}

export const isApplied = change => APPLIED.includes(change?.status);

export function displayedText(change) {
  return change.editedText != null ? change.editedText : change.updated;
}

export function changeForBullet(session, bulletId) {
  return session?.changes?.find(c => c.targetBulletId === bulletId) || null;
}

/** Port of computeAdjustedAfterScore: "after" reflects approved changes only. */
export function adjustedAfterScore(session) {
  if (!session) return 0;
  if (!session.changes.length) return session.matchBefore;
  const applied = session.changes.filter(isApplied).length / session.changes.length;
  return Math.round(session.matchBefore + (session.matchAfter - session.matchBefore) * applied);
}

/** Port of buildTailoredProfile — preview only (server is authoritative). */
export function tailoredPreview(profile, session) {
  if (!profile) return null;
  const text = (id, original) => {
    const change = changeForBullet(session, id);
    return change && isApplied(change) && (change.original || '').trim() === (original || '').trim()
      ? displayedText(change) : original;
  };
  return {
    ...profile,
    summary: { ...profile.summary, text: text('summary', profile.summary?.text || '') },
    experience: (profile.experience || []).map(exp => ({
      ...exp,
      bullets: (exp.bullets || []).map(b => ({ ...b, text: text(b.id, b.text) }))
    }))
  };
}

/** Port of changeReview.alternatePhrasing (re-validated by the server before use). */
export function alternatePhrasing(change) {
  const kw = change.keywordsAdded?.[0] || '';
  return `${change.original.replace(/\.$/, '')} — strengthened with ${kw ? `${kw} and ` : ''}measurable impact drawn directly from verified project work.`;
}

export function emptyProfile() {
  return {
    personalInformation: { fullName: '', email: '', phone: '', location: '', linkedIn: '', portfolio: '' },
    summary: { text: '', status: 'user-added' },
    skills: [],
    experience: [],
    education: [],
    certifications: [],
    awards: []
  };
}

export function changeLabel(change) {
  return change.company
    ? `${change.section} — ${change.company}${change.bulletLabel ? ` | ${change.bulletLabel}` : ''}`
    : change.section;
}

export function coverage(keywords, importance) {
  const rows = (keywords || []).filter(k => k.importance.toLowerCase() === importance);
  if (!rows.length) return { pct: null, matched: 0, total: 0 };
  const matched = rows.filter(k => k.status === 'Verified').length;
  return { pct: Math.round((matched / rows.length) * 100), matched, total: rows.length };
}
