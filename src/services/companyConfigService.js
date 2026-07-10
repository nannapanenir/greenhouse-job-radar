/**
 * Company Configuration Service
 * Loads Greenhouse company configuration from the Vercel serverless API.
 * Falls back to the local JSON config during local development only.
 */

import localCompaniesConfig from '../config/greenhouse-companies.json';

/**
 * Load company configuration from `/api/companies`.
 * Falls back to the local config only when running in Vite dev mode and the
 * API is unavailable. In production, a failure throws a clear error.
 *
 * @returns {Promise<Array<{name: string, token: string, enabled: boolean}>>}
 */
export async function getCompanies() {
  try {
    const response = await fetch('/api/companies');

    if (!response.ok) {
      throw new Error(`Company config request failed: ${response.status}`);
    }

    const data = await response.json();

    if (!data || !Array.isArray(data.companies)) {
      throw new Error('Company config response is not an array');
    }

    return data.companies;
  } catch (error) {
    if (import.meta.env.DEV === true) {
      console.warn('Falling back to local company configuration in dev mode:', error.message);
      return localCompaniesConfig;
    }
    throw new Error('Unable to load company configuration.');
  }
}
