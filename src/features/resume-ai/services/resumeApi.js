/**
 * Client for the Python API (backend/). The browser never talks to an AI
 * provider directly and never sees an API key.
 */

// Must match backend/resume/parser.py MAX_FILE_BYTES (below Vercel's 4.5 MB request limit).
export const MAX_UPLOAD_BYTES = 4 * 1024 * 1024;
export const MAX_UPLOAD_LABEL = '4 MB';

async function request(path, { method = 'GET', body, form } = {}) {
  let response;
  try {
    response = await fetch(path, {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: form || (body ? JSON.stringify(body) : undefined)
    });
  } catch {
    throw new Error('Could not reach the Job Radar Python API. Start it with: uvicorn backend.main:app --port 8000');
  }
  if (!response.ok) {
    let message = `Request failed (${response.status}).`;
    try {
      const data = await response.json();
      const detail = data.detail;
      message = typeof detail === 'string' ? detail
        : detail?.message || (Array.isArray(detail) ? detail.map(d => d.msg).join('; ') : message);
    } catch {
      if (response.status === 404) message = 'The Job Radar Python API is not available at this address.';
      if (response.status === 413) message = `File is too large (max ${MAX_UPLOAD_LABEL}).`;
    }
    const error = new Error(message);
    error.status = response.status;
    throw error;
  }
  return response;
}

const json = async (path, options) => (await request(path, options)).json();

function fileForm(file) {
  if (file.size > MAX_UPLOAD_BYTES) {
    throw new Error(`"${file.name}" is too large (max ${MAX_UPLOAD_LABEL}).`);
  }
  const form = new FormData();
  form.append('file', file);
  return form;
}

function filenameFrom(response, fallback) {
  const match = /filename="([^"]+)"/.exec(response.headers.get('Content-Disposition') || '');
  return match ? match[1] : fallback;
}

export const resumeApi = {
  health: () => json('/api/health'),
  aiStatus: () => json('/api/ai/status'),
  saveAISettings: settings => json('/api/ai/settings', { method: 'POST', body: settings }),
  clearAISettings: () => json('/api/ai/settings', { method: 'DELETE' }),

  parseResume: file => json('/api/resume/parse', { method: 'POST', form: fileForm(file) }),
  extractText: file => json('/api/resume/extract-text', { method: 'POST', form: fileForm(file) }),

  analyze: ({ profile, job }) => json('/api/resume/analyze', {
    method: 'POST', body: { candidateProfile: profile, job }
  }),
  tailor: ({ profile, job, mode, preferences }) => json('/api/resume/tailor', {
    method: 'POST', body: { candidateProfile: profile, job, mode, preferences }
  }),
  checkChange: ({ profile, change, jdKeywords, jobTitle }) => json('/api/resume/check-change', {
    method: 'POST', body: { candidateProfile: profile, change, jdKeywords, jobTitle: jobTitle || '' }
  }),
  chat: ({ message, profile, session, job, activeChangeId }) => json('/api/resume/chat', {
    method: 'POST', body: { message, candidateProfile: profile, session, job, activeChangeId }
  }),

  async generate({ profile, session, format }) {
    const response = await request('/api/resume/generate', {
      method: 'POST', body: { candidateProfile: profile, session, format }
    });
    return {
      blob: await response.blob(),
      filename: filenameFrom(response, `tailored-resume.${format}`),
      appliedChangeIds: (response.headers.get('X-Applied-Changes') || '').split(',').filter(Boolean),
      userOverrides: (response.headers.get('X-User-Overrides') || '').split(',').filter(Boolean),
      skipped: Number(response.headers.get('X-Skipped-Changes') || 0)
    };
  }
};
