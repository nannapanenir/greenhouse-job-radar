/**
 * Role Profile Service
 * Loads and saves switchable role profiles (keyword sets) in localStorage,
 * and resolves the active profile from the URL, last used, or default.
 */

import roleProfilesConfig from '../config/role-profiles.json';

const PROFILES_STORAGE_KEY = 'aiJobRadar_roleProfiles';
const ACTIVE_PROFILE_STORAGE_KEY = 'aiJobRadar_activeRoleProfile';
const ROLE_URL_PARAM = 'role';

export const LOCATION_KEYWORDS = roleProfilesConfig.locationKeywords;

function readStorage(key) {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeStorage(key, value) {
  try {
    localStorage.setItem(key, value);
  } catch {
    // Storage unavailable (private mode, quota, blocked) - ignore
  }
}

function removeStorage(key) {
  try {
    localStorage.removeItem(key);
  } catch {
    // Storage unavailable - ignore
  }
}

/**
 * Deep copy of the profiles shipped in role-profiles.json
 */
export function getDefaultProfiles() {
  return roleProfilesConfig.profiles.map(profile => ({
    ...profile,
    includeKeywords: [...profile.includeKeywords],
    excludeTitleKeywords: [...profile.excludeTitleKeywords]
  }));
}

/**
 * Convert a name into a URL-safe id, e.g. "AI / LLM Engineer" -> "ai-llm-engineer"
 */
export function slugify(text) {
  return String(text || '')
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

/**
 * Split free text into a keyword list on commas and newlines.
 * Wrap a keyword in double quotes to keep a comma inside it,
 * e.g. "Software Engineer, Web". Trims, drops empties, and de-duplicates
 * case-insensitively.
 */
export function parseKeywordList(text) {
  const tokens = String(text || '').match(/"[^"]*"|[^,\n]+/g) || [];
  const seen = new Set();
  const keywords = [];

  for (const token of tokens) {
    const keyword = token.trim().replace(/^"|"$/g, '').trim();
    const key = keyword.toLowerCase();
    if (keyword && !seen.has(key)) {
      seen.add(key);
      keywords.push(keyword);
    }
  }

  return keywords;
}

/**
 * Inverse of parseKeywordList: one keyword per line, quoting any with commas
 */
export function formatKeywordList(keywords = []) {
  return keywords.map(kw => (kw.includes(',') ? `"${kw}"` : kw)).join('\n');
}

function isStringArray(value) {
  return Array.isArray(value) && value.every(item => typeof item === 'string');
}

function isValidProfile(profile) {
  return (
    profile &&
    typeof profile.id === 'string' && profile.id !== '' &&
    typeof profile.name === 'string' && profile.name.trim() !== '' &&
    isStringArray(profile.includeKeywords) && profile.includeKeywords.length > 0 &&
    isStringArray(profile.excludeTitleKeywords)
  );
}

/**
 * Load profiles from localStorage, falling back to config defaults
 */
export function loadProfiles() {
  const stored = readStorage(PROFILES_STORAGE_KEY);
  if (stored) {
    try {
      const parsed = JSON.parse(stored);
      if (Array.isArray(parsed) && parsed.length > 0 && parsed.every(isValidProfile)) {
        return parsed.map(profile => ({
          ...profile,
          searchDescription: profile.searchDescription === true
        }));
      }
    } catch {
      // Corrupt JSON - fall through to defaults
    }
  }
  return getDefaultProfiles();
}

export function saveProfiles(profiles) {
  writeStorage(PROFILES_STORAGE_KEY, JSON.stringify(profiles));
}

/**
 * Clear saved profiles and return the config defaults
 */
export function resetProfiles() {
  removeStorage(PROFILES_STORAGE_KEY);
  return getDefaultProfiles();
}

function getUrlProfileId() {
  try {
    return new URLSearchParams(window.location.search).get(ROLE_URL_PARAM);
  } catch {
    return null;
  }
}

/**
 * Resolve the active profile id: ?role= URL param, then last used, then default
 */
export function resolveActiveProfileId(profiles) {
  const ids = new Set(profiles.map(p => p.id));
  const candidates = [
    getUrlProfileId(),
    readStorage(ACTIVE_PROFILE_STORAGE_KEY),
    roleProfilesConfig.defaultProfileId
  ];

  for (const id of candidates) {
    if (id && ids.has(id)) return id;
  }

  return profiles[0]?.id ?? null;
}

/**
 * Persist the active profile id and mirror it into ?role= without a navigation
 */
export function saveActiveProfileId(id) {
  if (!id) return;
  writeStorage(ACTIVE_PROFILE_STORAGE_KEY, id);

  try {
    const url = new URL(window.location.href);
    if (url.searchParams.get(ROLE_URL_PARAM) !== id) {
      url.searchParams.set(ROLE_URL_PARAM, id);
      window.history.replaceState(window.history.state, '', url);
    }
  } catch {
    // History API unavailable - ignore
  }
}

/**
 * Build a unique id for a new profile from its name
 */
export function createProfileId(name, profiles) {
  const base = slugify(name) || 'role';
  const ids = new Set(profiles.map(p => p.id));
  let id = base;
  let suffix = 2;
  while (ids.has(id)) {
    id = `${base}-${suffix++}`;
  }
  return id;
}
