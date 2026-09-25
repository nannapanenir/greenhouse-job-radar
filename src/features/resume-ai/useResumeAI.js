/**
 * Resume AI state + operations. Every AI-backed action goes through the
 * Python API; the Master Resume / Candidate Profile is never modified by
 * tailoring (only by explicit edits in Career Profile).
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { manualJob } from '../../shared/models/commonJob';
import { resumeApi } from './services/resumeApi';
import { addHistory, clearWorkspace, loadHistory, loadWorkspace, saveWorkspace, takePendingJob } from './services/resumeStore';
import { adjustedAfterScore, alternatePhrasing, displayedText, isApplied } from './logic';

const INITIAL = {
  apiStatus: 'checking', // checking | online | offline
  aiStatus: null,
  masterResume: null,
  profile: null,
  job: null,
  mode: 'balanced',
  analysis: null,
  session: null,
  activeChangeIndex: 0,
  chatLog: [],
  busy: null,
  error: null,
  notice: null
};

const time = () => new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

function summarize(session) {
  const parts = [];
  if (session.changes.length === 0) {
    parts.push(`I compared this job to your verified profile. Estimated relevance is ${session.matchBefore}%. I couldn't find a truthful way to strengthen any line without adding unverified claims.`);
  } else {
    parts.push(`Done. Estimated relevance moves from ${session.matchBefore}% to ${session.matchAfter}% based on ${session.changes.length} proposed change${session.changes.length > 1 ? 's' : ''}. Review each one in the Changes tab.`);
  }
  if (session.blockedChanges?.length) {
    parts.push(`${session.blockedChanges.length} suggestion(s) were blocked by the truth validator (see Changes → Blocked).`);
  }
  if (session.stillMissing?.length) {
    parts.push(`Still missing (not added): ${session.stillMissing.map(m => m.skill).join(', ')}.`);
  }
  (session.warnings || []).forEach(w => parts.push(w));
  return parts.join('\n');
}

function download(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function useResumeAI({ incoming } = {}) {
  const [state, setState] = useState(() => ({ ...INITIAL, ...loadWorkspace(), busy: null, error: null }));
  const [history, setHistory] = useState(loadHistory);
  const ref = useRef(state);
  ref.current = state;

  const patch = useCallback(update => {
    setState(prev => ({ ...prev, ...(typeof update === 'function' ? update(prev) : update) }));
  }, []);

  const say = useCallback((role, text) => {
    setState(prev => ({ ...prev, chatLog: [...prev.chatLog, { role, text, time: time() }] }));
  }, []);

  // Persist (no secrets in this state).
  useEffect(() => { saveWorkspace(state); }, [state]);

  const refreshStatus = useCallback(async () => {
    try {
      const [, ai] = await Promise.all([resumeApi.health(), resumeApi.aiStatus()]);
      patch({ apiStatus: 'online', aiStatus: ai });
    } catch {
      patch({ apiStatus: 'offline' });
    }
  }, [patch]);

  useEffect(() => { refreshStatus(); }, [refreshStatus]);

  const run = useCallback(async (label, fn) => {
    patch({ busy: label, error: null });
    try {
      return await fn();
    } catch (error) {
      patch({ error: error.message });
      say('assistant', error.message);
      return null;
    } finally {
      patch({ busy: null });
    }
  }, [patch, say]);

  // ---- Job selection -------------------------------------------------------

  const setJob = useCallback(job => {
    patch({ job, session: null, analysis: null, activeChangeIndex: 0, error: null });
    if (job) {
      say('assistant', job.source === 'manual'
        ? 'Job description received.'
        : `Selected from Job Radar: ${job.title}${job.company ? ` at ${job.company}` : ''} (${job.source}). The job description is loaded — no copy/paste needed.`);
    }
  }, [patch, say]);

  // "Tailor Resume" hand-off from the Jobs page ({ job, at } so re-selecting the same job works).
  useEffect(() => {
    const pending = takePendingJob();
    const job = incoming?.job || pending;
    if (job && (job.id !== ref.current.job?.id || incoming)) setJob(job);
  }, [incoming, setJob]);

  const setManualJobDescription = useCallback(text => {
    if (!text?.trim()) return;
    setJob(manualJob(text.trim()));
  }, [setJob]);

  const uploadJobDescription = useCallback(file => run('Reading job description…', async () => {
    const { text } = await resumeApi.extractText(file);
    say('user', `📥 Uploaded job description: ${file.name}`);
    setManualJobDescription(text);
  }), [run, say, setManualJobDescription]);

  // ---- Master resume / profile -------------------------------------------

  const uploadResume = useCallback(file => run(`Extracting your career profile from "${file.name}"… (free/local models can take a minute)`, async () => {
    const { profile, masterResume } = await resumeApi.parseResume(file);
    patch({ profile, masterResume, session: null, analysis: null });
    say('assistant', `I extracted your career profile from "${file.name}". Everything is marked "Extracted" — review it under Career Profile, then pick a job to tailor for. This is now your Master Resume; tailoring never changes it.`);
  }), [run, patch, say]);

  const updateProfile = useCallback(updater => {
    patch(prev => ({ profile: updater(structuredClone(prev.profile)) }));
  }, [patch]);

  // ---- Analysis / tailoring (core functions shared by buttons and chat) ----

  async function analyzeCore() {
    const { profile, job } = ref.current;
    if (!profile || !job) throw new Error('Upload your master resume and choose a job first.');
    const analysis = await resumeApi.analyze({ profile, job });
    patch({ analysis });
    say('assistant', `Estimated relevance for ${analysis.jobTitle}: ${analysis.matchBefore}%.\nVerified matches: ${analysis.strongMatches.join(', ') || 'none'}.\nMissing (won't be added): ${analysis.stillMissing.map(m => m.skill).join(', ') || 'none'}.`);
    return analysis;
  }

  async function tailorCore({ preferences = {}, mode, job: jobOverride } = {}) {
    const profile = ref.current.profile;
    const job = jobOverride || ref.current.job;
    if (!profile) throw new Error('Upload your master resume first (Resume AI → Upload Master Resume).');
    if (!job) throw new Error('Choose a job in Job Radar, or paste/upload a job description.');
    const useMode = mode || ref.current.mode;
    const session = await resumeApi.tailor({ profile, job, mode: useMode, preferences });
    patch({ session, mode: useMode, activeChangeIndex: 0 });
    say('assistant', summarize(session));
    return session;
  }

  const analyze = () => run('Analyzing your fit…', analyzeCore);
  const tailor = (options = {}) => run('Tailoring your resume…', () => tailorCore(options));

  // ---- Change review ------------------------------------------------------

  const updateChange = useCallback((id, changes) => {
    patch(prev => ({
      session: prev.session && {
        ...prev.session,
        changes: prev.session.changes.map(c => (c.id === id ? { ...c, ...changes } : c))
      }
    }));
  }, [patch]);

  const accept = useCallback(change => updateChange(change.id, { status: change.editedText != null ? 'edited' : 'accepted' }), [updateChange]);
  const reject = useCallback(change => updateChange(change.id, { status: 'rejected' }), [updateChange]);
  const restore = useCallback(change => updateChange(change.id, { status: 'pending', editedText: null, userFlagged: null }), [updateChange]);

  const acceptAllSafe = useCallback(() => {
    // Every change shown has passed the server's truth validator ("safe").
    const count = (ref.current.session?.changes || []).filter(c => c.status === 'pending').length;
    patch(prev => ({
      session: prev.session && {
        ...prev.session,
        changes: prev.session.changes.map(c => (c.status === 'pending' ? { ...c, status: 'accepted' } : c))
      }
    }));
    return count;
  }, [patch]);

  /** Validate a user edit on the server; returns reasons (empty = supported). */
  const checkText = useCallback(async (change, text) => {
    const { profile, session } = ref.current;
    const result = await resumeApi.checkChange({
      profile,
      change: { ...change, editedText: text },
      jdKeywords: (session?.keywords || []).map(k => k.keyword)
    });
    return result.reasons;
  }, []);

  const saveEdit = useCallback((change, text, reasons = []) => {
    updateChange(change.id, { editedText: text, status: 'edited', userFlagged: reasons.length ? reasons : null });
  }, [updateChange]);

  const regenerate = useCallback(change => run('Checking alternate phrasing…', async () => {
    const candidate = alternatePhrasing(change);
    const reasons = await checkText(change, candidate);
    if (reasons.length) {
      say('assistant', `I didn't use an alternate phrasing for "${change.bulletLabel || change.section}" because it wouldn't be supported: ${reasons.join(' ')}`);
      return;
    }
    const variants = change.variants || [change.updated];
    updateChange(change.id, {
      variants: variants.includes(candidate) ? variants : [...variants, candidate],
      updated: change.updated === candidate ? variants[0] : candidate,
      editedText: null,
      status: 'pending'
    });
  }), [run, checkText, updateChange, say]);

  const setActiveChangeIndex = useCallback(index => patch({ activeChangeIndex: index }), [patch]);

  // ---- Generation -----------------------------------------------------------

  async function generateCore(format) {
    const { profile, session, job, mode } = ref.current;
    if (!profile) throw new Error('Upload your master resume first.');
    const result = await resumeApi.generate({ profile, session, format });
    download(result.blob, result.filename);
    if (session) {
      const jobId = job?.id || '';
      const entry = {
        id: `tr-${Date.now()}`,
        jobId,
        company: job?.company || '',
        title: session.jobTitle || job?.title || '',
        applyUrl: job?.applyUrl || null,
        source: job?.source || 'manual',
        createdAt: new Date().toISOString(),
        format,
        mode,
        appliedChangeIds: result.appliedChangeIds,
        matchBefore: session.matchBefore,
        matchAfter: adjustedAfterScore(session),
        filename: result.filename,
        resumeVersion: loadHistory().filter(h => h.jobId === jobId).length + 1
      };
      setHistory(addHistory(entry));
    }
    say('assistant', `Downloaded ${result.filename} with ${result.appliedChangeIds.length} approved change(s).${result.skipped ? ` ${result.skipped} change(s) were skipped because the original line changed.` : ''} Your Master Resume is unchanged.`);
    return result;
  }

  const generate = format => run(`Generating ${format.toUpperCase()}…`, () => generateCore(format));

  // ---- Chat (controlled operations only) ---------------------------------

  const sendChat = message => run('Thinking…', async () => {
    const text = message.trim();
    if (!text) return;
    say('user', text.length > 220 ? `${text.replace(/\s+/g, ' ').slice(0, 220)}…` : text);
    const { profile, session, job, activeChangeIndex } = ref.current;
    const activeChangeId = session?.changes?.[Math.min(activeChangeIndex, (session?.changes?.length || 1) - 1)]?.id;
    const { operation, reply, params } = await resumeApi.chat({ message: text, profile, session, job, activeChangeId });

    switch (operation) {
      case 'set_job_description': {
        const newJob = manualJob(params.jobDescriptionText);
        setJob(newJob);
        return tailorCore({ job: newJob });
      }
      case 'analyze_job':
        return ref.current.job ? analyzeCore() : say('assistant', reply);
      case 'tailor_resume':
        return ref.current.job ? tailorCore() : say('assistant', reply);
      case 'adjust_tailoring':
        say('assistant', reply);
        if (params.preferences || params.mode) {
          return tailorCore({ preferences: params.preferences || {}, mode: params.mode || undefined });
        }
        return undefined;
      case 'generate_resume':
        say('assistant', reply);
        return generateCore(params.format || 'docx');
      case 'explain_change': {
        const index = (ref.current.session?.changes || []).findIndex(c => c.id === params.changeId);
        if (index >= 0) patch({ activeChangeIndex: index });
        return say('assistant', reply);
      }
      default:
        return say('assistant', reply);
    }
  });

  // ---- Settings ---------------------------------------------------------------

  const setMode = useCallback(mode => patch({ mode }), [patch]);

  const saveAISettings = useCallback(settings => run('Saving AI settings…', async () => {
    const aiStatus = await resumeApi.saveAISettings(settings);
    patch({ aiStatus });
    return aiStatus;
  }), [run, patch]);

  const clearAISettings = useCallback(() => run('Disconnecting…', async () => {
    patch({ aiStatus: await resumeApi.clearAISettings() });
  }), [run, patch]);

  const resetWorkspace = useCallback(() => {
    clearWorkspace();
    setState({ ...INITIAL, apiStatus: ref.current.apiStatus, aiStatus: ref.current.aiStatus });
  }, []);

  return {
    state,
    history,
    actions: {
      refreshStatus, setJob, setManualJobDescription, uploadJobDescription, uploadResume, updateProfile,
      analyze, tailor, accept, reject, restore, acceptAllSafe, checkText, saveEdit, regenerate,
      setActiveChangeIndex, generate, sendChat, setMode, saveAISettings, clearAISettings, resetWorkspace,
      dismissError: () => patch({ error: null })
    },
    helpers: { displayedText, isApplied, adjustedAfterScore }
  };
}
