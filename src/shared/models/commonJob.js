/**
 * Phase 1 Common Job contract, shared by Jobs and Resume AI.
 * Resume AI only ever sees this shape, whatever the job's source.
 */

export const SOURCE_LABELS = {
  greenhouse: 'Greenhouse',
  lever: 'Lever',
  ashby: 'Ashby',
  manual: 'Manual'
};

const NO_LOCATION = 'Location Not Provided';

/** UI job (legacy Greenhouse flow or toUiJob output) -> Common Job. */
export function toCommonJob(uiJob) {
  const source = uiJob.source || 'greenhouse';
  const companyKey = uiJob.companyToken || '';
  const sourceJobId = uiJob.id != null ? String(uiJob.id) : '';
  return {
    id: uiJob.globalId || `${source}:${companyKey}:${sourceJobId}`,
    source,
    sourceJobId,
    company: uiJob.companyName || '',
    companyKey,
    title: uiJob.title || '',
    location: uiJob.location && uiJob.location !== NO_LOCATION ? uiJob.location : null,
    description: uiJob.cleanContent || '',
    postedAt: uiJob.postedAt || null,
    updatedAt: uiJob.updatedAt || null,
    applyUrl: uiJob.absoluteUrl || null,
    sourceUrl: uiJob.sourceUrl || uiJob.absoluteUrl || null,
    metadata: uiJob.metadata || {}
  };
}

/** A pasted/uploaded job description (not from Job Radar). */
export function manualJob(text) {
  const firstLine = (text || '').split('\n').map(l => l.trim()).find(Boolean) || 'Job description';
  return {
    id: `manual:${Date.now()}`,
    source: 'manual',
    sourceJobId: '',
    company: '',
    companyKey: '',
    title: firstLine.slice(0, 120),
    location: null,
    description: text,
    postedAt: null,
    updatedAt: null,
    applyUrl: null,
    sourceUrl: null,
    metadata: {}
  };
}
