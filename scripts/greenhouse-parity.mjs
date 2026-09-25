#!/usr/bin/env node
/**
 * Greenhouse parity check: existing frontend flow vs Python agent.
 *
 *   node scripts/greenhouse-parity.mjs [--fixtures DIR] [--sources FILE]
 *
 * 1. Runs the EXISTING src/services/greenhouseService.js (unchanged, bundled
 *    with esbuild) with fetch mocked to serve DIR/greenhouse/<token>.json.
 * 2. Runs `python agent/main.py --fixtures DIR --only greenhouse`.
 * 3. Maps agent jobs through toUiJob() and compares every UI field, company
 *    success/failure lists, role-profile matches, and cleanHtmlContent output.
 *
 * Exit code 0 = identical, 1 = differences (printed), 2 = setup error.
 * To check against live data, record fixtures first:
 *   python agent/main.py --only greenhouse --save-fixtures /tmp/gh
 *   node scripts/greenhouse-parity.mjs --fixtures /tmp/gh --sources /tmp/gh/sources.json
 */

import { build } from 'esbuild';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync, writeFileSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const args = process.argv.slice(2);
const argValue = (name, fallback) => {
  const i = args.indexOf(name);
  return i >= 0 && args[i + 1] ? resolve(args[i + 1]) : fallback;
};
const FIXTURES = argValue('--fixtures', join(ROOT, 'tests/agent/fixtures'));
const SOURCES = argValue('--sources', join(FIXTURES, 'sources.json'));
const PYTHON = process.env.PYTHON || 'python3';

/**
 * Intentional, documented differences (see agent/README.md). The legacy flow
 * turns a location object with an empty name into the object itself
 * (`location?.name || location`), which never matches the location filter, so
 * the job is silently dropped. The agent treats it as "no location" and keeps
 * it, matching the legacy intent ("jobs with no location are kept").
 */
function expectedAgentOnlyUrls(companies) {
  const urls = new Set();
  for (const company of companies) {
    const file = join(FIXTURES, 'greenhouse', `${company.token ?? company.key}.json`);
    if (!existsSync(file)) continue;
    for (const raw of JSON.parse(readFileSync(file, 'utf8')).jobs || []) {
      const loc = raw.location;
      if (loc && typeof loc === 'object' && !loc.name) urls.add(raw.absolute_url);
    }
  }
  return urls;
}

const UI_FIELDS = ['companyName', 'companyToken', 'title', 'location', 'updatedAt', 'absoluteUrl', 'cleanContent', 'jobAgeText', 'freshnessLevel'];

// Tricky inputs for cleanHtmlContent (JS) vs clean_html_content (Python).
const HTML_CASES = [
  null, '', 'plain text',
  '&lt;p&gt;Escaped &amp;amp; double&amp;nbsp;escaped&lt;/p&gt;',
  '<P>Upper</P><BR/><br >x<h3 class="a">Head</h3>',
  '<ul><li>a</li><li data-x="1">b</li></ul>\n\n\n\n<p>gap</p>',
  'tabs\t\tand   spaces &#8212; &#233; &#x1F600; &#X41; &#65536; &#xD800;',
  '&nbsp;&nbsp;lead/trail ﻿ ',
  '<div><div></div></div><p>&ldquo;quotes&rdquo; &lsquo;x&rsquo; &ndash; &mdash;</p>',
  '<script>alert(1)</script>< not a tag > a<b'
];

function fail(message) {
  console.error(`SETUP ERROR: ${message}`);
  process.exit(2);
}

async function loadFrontendModules(workDir) {
  const entry = join(workDir, 'entry.js');
  writeFileSync(entry, `
    export { fetchAllJobs } from ${JSON.stringify(join(ROOT, 'src/services/greenhouseService.js'))};
    export { applyRoleProfile } from ${JSON.stringify(join(ROOT, 'src/utils/jobFilters.js'))};
    export { cleanHtmlContent } from ${JSON.stringify(join(ROOT, 'src/utils/htmlCleaner.js'))};
    export { getDefaultProfiles } from ${JSON.stringify(join(ROOT, 'src/services/roleProfileService.js'))};
    export { toUiJob } from ${JSON.stringify(join(ROOT, 'src/services/agentJobsService.js'))};
  `);
  const outfile = join(workDir, 'bundle.mjs');
  await build({ entryPoints: [entry], bundle: true, format: 'esm', platform: 'node', outfile, logLevel: 'error' });
  return import(pathToFileURL(outfile).href);
}

function mockGreenhouseFetch() {
  globalThis.fetch = async (url) => {
    const match = String(url).match(/\/v1\/boards\/([^/]+)\/jobs/);
    const file = match && join(FIXTURES, 'greenhouse', `${decodeURIComponent(match[1])}.json`);
    if (!file || !existsSync(file)) {
      return { ok: false, status: 404, statusText: 'Not Found', json: async () => ({}) };
    }
    const body = JSON.parse(readFileSync(file, 'utf8'));
    return { ok: true, status: 200, statusText: 'OK', json: async () => body };
  };
}

function runAgent(workDir) {
  const output = join(workDir, 'jobs.json');
  const result = spawnSync(PYTHON, [
    join(ROOT, 'agent/main.py'), '--fixtures', FIXTURES, '--sources', SOURCES,
    '--only', 'greenhouse', '--output', output, '--quiet'
  ], { encoding: 'utf8' });
  if (result.status !== 0) fail(`agent exited ${result.status}\n${result.stderr}`);
  return JSON.parse(readFileSync(output, 'utf8'));
}

function pythonClean(inputs) {
  const code = [
    'import json, sys',
    `sys.path.insert(0, ${JSON.stringify(ROOT)})`,
    'from agent.processing.normalizer import clean_html_content',
    'print(json.dumps([clean_html_content(x) for x in json.load(sys.stdin)]))'
  ].join('\n');
  const result = spawnSync(PYTHON, ['-c', code], { input: JSON.stringify(inputs), encoding: 'utf8' });
  if (result.status !== 0) fail(`python cleaner failed\n${result.stderr}`);
  return JSON.parse(result.stdout);
}

// JS fromCharCode can yield lone surrogates, which JSON/UTF-8 can't carry; the
// Python port emits U+FFFD for them. Normalise before comparing.
const wellFormed = (s) => (typeof s === 'string' ? s.replace(/[\uD800-\uDFFF]/g, '�') : s);

async function main() {
  if (!existsSync(SOURCES)) fail(`sources file not found: ${SOURCES}`);
  const sources = JSON.parse(readFileSync(SOURCES, 'utf8'));
  const companies = sources.greenhouse;
  if (!Array.isArray(companies)) fail(`${SOURCES} has no "greenhouse" array`);

  const workDir = mkdtempSync(join(tmpdir(), 'gh-parity-'));
  const problems = [];
  const diff = (where, legacy, agent) => {
    if (JSON.stringify(legacy) !== JSON.stringify(agent)) {
      problems.push(`${where}\n    legacy: ${JSON.stringify(legacy)}\n    agent:  ${JSON.stringify(agent)}`);
    }
  };

  try {
    const fe = await loadFrontendModules(workDir);
    mockGreenhouseFetch();
    const legacy = await fe.fetchAllJobs(companies);
    const agentData = runAgent(workDir);
    const agentOnly = expectedAgentOnlyUrls(companies);
    const intentional = agentData.jobs.filter(j => agentOnly.has(j.applyUrl));
    const agentJobs = agentData.jobs.filter(j => !agentOnly.has(j.applyUrl)).map(fe.toUiJob);

    // Jobs: same order, same UI fields
    diff('job count', legacy.jobs.length, agentJobs.length);
    const n = Math.min(legacy.jobs.length, agentJobs.length);
    for (let i = 0; i < n; i++) {
      const a = legacy.jobs[i];
      const b = agentJobs[i];
      diff(`job[${i}].id`, String(a.id), String(b.id));
      for (const field of UI_FIELDS) diff(`job[${i}] (${a.absoluteUrl}).${field}`, a[field], b[field]);
    }

    // Companies
    diff('totalCompaniesSearched', legacy.totalCompaniesSearched, agentData.statistics.companiesSearched);
    const extraByKey = {};
    intentional.forEach(j => { extraByKey[j.companyKey] = (extraByKey[j.companyKey] || 0) + 1; });
    const agentOk = agentData.companies.filter(c => c.status === 'ok')
      .map(c => ({ name: c.name, token: c.key, totalJobs: c.jobsFetched, usJobs: c.jobsKept - (extraByKey[c.key] || 0) }));
    const agentFailed = agentData.companies.filter(c => c.status !== 'ok')
      .map(c => ({ name: c.name, token: c.key, error: c.error }));
    const byToken = (x, y) => x.token.localeCompare(y.token);
    diff('successfulCompanies', [...legacy.successfulCompanies].sort(byToken), agentOk.sort(byToken));
    diff('failedCompanies', [...legacy.failedCompanies].sort(byToken), agentFailed.sort(byToken));

    // Role profiles (client-side matching must give identical results)
    for (const profile of fe.getDefaultProfiles()) {
      for (const searchDescription of [false, true]) {
        const p = { ...profile, searchDescription };
        const pick = jobs => fe.applyRoleProfile(jobs, p).map(j => [j.absoluteUrl, j.matchedKeywords]);
        diff(`role ${profile.id} (searchDescription=${searchDescription})`, pick(legacy.jobs), pick(agentJobs));
      }
    }

    // HTML cleaner edge cases
    const py = pythonClean(HTML_CASES);
    HTML_CASES.forEach((input, i) => diff(`cleanHtmlContent(${JSON.stringify(input)})`, wellFormed(fe.cleanHtmlContent(input)), py[i]));

    const roleChecks = fe.getDefaultProfiles().length * 2;
    console.log(`Fixtures: ${FIXTURES}`);
    console.log(`Legacy jobs: ${legacy.jobs.length} | Agent jobs: ${agentJobs.length} | ` +
      `companies ok/failed: ${legacy.successfulCompanies.length}/${legacy.failedCompanies.length} | ` +
      `role checks: ${roleChecks} | cleaner cases: ${HTML_CASES.length}`);
    if (intentional.length) {
      console.log(`Intentional differences (agent keeps, legacy drops - empty location name): ${intentional.map(j => j.applyUrl).join(', ')}`);
    }
    if (problems.length) {
      console.log(`\nPARITY FAILED - ${problems.length} difference(s):`);
      problems.forEach(p => console.log(`  - ${p}`));
      process.exitCode = 1;
    } else {
      console.log('PARITY OK - Python Greenhouse output is identical to the existing frontend flow.');
    }
  } finally {
    rmSync(workDir, { recursive: true, force: true });
  }
}

main().catch(error => fail(error.stack || error.message));
