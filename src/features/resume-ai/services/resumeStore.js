/**
 * Local-first persistence for Resume AI (swap this module for a database
 * later). Stores the Master Resume metadata, the Candidate Profile, the
 * current job/session and safe preferences. NEVER stores API keys — those
 * stay on the Python server.
 */

import { readJson, removeKey, writeJson } from '../../../shared/services/storage';

const WORKSPACE_KEY = 'jobRadar_resumeAI_workspace_v1';
const HISTORY_KEY = 'jobRadar_resumeAI_history_v1';
const PENDING_JOB_KEY = 'jobRadar_resumeAI_pendingJob_v1';
const MAX_CHAT = 100;

const PERSISTED = ['masterResume', 'profile', 'job', 'mode', 'session', 'analysis', 'activeChangeIndex', 'chatLog'];

export function loadWorkspace() {
  return readJson(WORKSPACE_KEY, {}) || {};
}

export function saveWorkspace(state) {
  const data = {};
  PERSISTED.forEach(key => { data[key] = state[key] ?? null; });
  data.chatLog = (state.chatLog || []).slice(-MAX_CHAT);
  writeJson(WORKSPACE_KEY, data);
}

export function clearWorkspace() {
  removeKey(WORKSPACE_KEY);
}

/** Tailored resume versions: which resume was generated for which job. */
export function loadHistory() {
  return readJson(HISTORY_KEY, []) || [];
}

export function addHistory(entry) {
  const history = [entry, ...loadHistory()].slice(0, 200);
  writeJson(HISTORY_KEY, history);
  return history;
}

/** Hand-off from the Jobs page ("Tailor Resume") to Resume AI. */
export function setPendingJob(job) {
  writeJson(PENDING_JOB_KEY, job);
}

export function takePendingJob() {
  const job = readJson(PENDING_JOB_KEY, null);
  removeKey(PENDING_JOB_KEY);
  return job;
}
