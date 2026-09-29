/**
 * End-to-end: Job Radar jobs (Greenhouse/Lever/Ashby) -> Tailor Resume -> Resume AI.
 *
 *   NODE_PATH=$(npm root -g) node tests/e2e/resume-ai.e2e.mjs
 *
 * Starts: a fake OpenAI-compatible "local model", the Python API
 * (AI_PROVIDER=local; job providers served from the Phase 1 fixtures via the
 * dev-only JOB_FETCH_FIXTURES_DIR) and the Vite dev server; then drives
 * Chromium with Playwright and inspects the browser's network traffic.
 * Auth (Phase 3A): a fake Supabase Auth server backs /api/auth/*; the browser
 * must only ever talk to /api/auth and hold the session in HttpOnly cookies.
 */

import { spawn, spawnSync } from 'node:child_process';
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const PY = process.env.PYTHON || 'python3';
const SECRET = 'sk-local-E2E-SECRET-DO-NOT-LEAK';
const PORTS = { ai: 8765, supabase: 8766, api: 8011, web: 5181 };
const tmp = mkdtempSync(join(tmpdir(), 'resume-ai-e2e-'));
const procs = [];
const results = [];

const check = (name, ok, detail = '') => {
  results.push({ name, ok, detail });
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? ` — ${detail}` : ''}`);
};

function start(cmd, args, env = {}) {
  const p = spawn(cmd, args, { cwd: ROOT, env: { ...process.env, ...env }, stdio: ['ignore', 'pipe', 'pipe'] });
  p.stderr.on('data', d => { if (process.env.E2E_DEBUG) process.stderr.write(d); });
  procs.push(p);
  return p;
}

async function waitFor(url, ms = 30000) {
  const end = Date.now() + ms;
  while (Date.now() < end) {
    try { if ((await fetch(url)).status < 500) return; } catch { /* retry */ }
    await new Promise(r => setTimeout(r, 300));
  }
  throw new Error(`timeout waiting for ${url}`);
}

async function main() {
  start(PY, ['tests/e2e/fake_ai_server.py', String(PORTS.ai)]);
  start(PY, ['tests/e2e/fake_supabase_server.py', String(PORTS.supabase)]);
  start(PY, ['-m', 'uvicorn', 'backend.main:app', '--port', String(PORTS.api)], {
    AI_PROVIDER: 'local', AI_MODEL: 'fake-local-model', LOCAL_AI_BASE_URL: `http://127.0.0.1:${PORTS.ai}/v1`,
    LOCAL_AI_API_KEY: SECRET, RESUME_AI_DATA_DIR: join(tmp, 'data'),
    SUPABASE_URL: `http://127.0.0.1:${PORTS.supabase}`, SUPABASE_PUBLISHABLE_KEY: 'sb_publishable_E2E_KEY',
    JOB_FETCH_FIXTURES_DIR: join(ROOT, 'tests/agent/fixtures'), JOB_SOURCES_FILE: join(ROOT, 'tests/agent/fixtures/sources.json'),
  });
  start('npx', ['vite', '--port', String(PORTS.web), '--strictPort'], { VITE_API_TARGET: `http://127.0.0.1:${PORTS.api}` });
  await waitFor(`http://127.0.0.1:${PORTS.api}/api/health`);
  await waitFor(`http://localhost:${PORTS.web}/`);

  const browser = await chromium.launch();
  const context = await browser.newContext({ acceptDownloads: true });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  const base = `http://localhost:${PORTS.web}`;

  // A role that shows jobs from all three sources, plus an existing saved status.
  await page.goto(base);
  await page.evaluate(() => {
    localStorage.setItem('aiJobRadar_roleProfiles', JSON.stringify([{ id: 'e2e', name: 'E2E', includeKeywords: ['Engineer', 'Strategist'], excludeTitleKeywords: [], searchDescription: false }]));
    localStorage.setItem('aiJobRadar_jobStatuses', JSON.stringify({ 'https://job-boards.greenhouse.io/anthropic/jobs/1001': 'Saved' }));
  });

  // 1. Upload master resume (fake local model extracts the profile)
  await page.goto(`${base}/resume-ai?role=e2e`);
  await page.getByTestId('api-status').filter({ hasText: 'online' }).waitFor();
  check('Resume AI shows API + local provider status', (await page.getByTestId('api-status').innerText()).includes('local / fake-local-model'));
  await page.getByTestId('master-resume-input').first().setInputFiles(join(ROOT, 'tests/backend/fixtures/sample_resume.docx'));
  await page.getByTestId('resume-preview').filter({ hasText: 'Alex Rivera' }).waitFor({ timeout: 20000 });
  check('DOCX master resume -> Python parse -> AI -> Candidate Profile', true);

  // 2. Jobs page: ONE refresh request; providers are fetched server-side (Greenhouse + Lever + Ashby)
  await page.getByRole('link', { name: 'Jobs' }).click();
  await page.getByRole('button', { name: 'All Jobs' }).click();
  const net = [];
  const onRequest = r => net.push({ method: r.method(), url: r.url() });
  page.on('request', onRequest);
  await page.getByRole('button', { name: /Fetch Latest Jobs/ }).click();
  await page.locator('h3', { hasText: 'Applied AI Engineer' }).waitFor();
  await page.getByTestId('refresh-summary').waitFor();
  page.off('request', onRequest);
  const refreshCalls = net.filter(r => r.url.endsWith('/api/jobs/refresh'));
  const providerCalls = net.filter(r => /greenhouse\.io|lever\.co|ashbyhq\.com/.test(r.url));
  check('Fetch button makes exactly one POST /api/jobs/refresh', refreshCalls.length === 1 && refreshCalls[0].method === 'POST',
    `${refreshCalls.length} refresh call(s)`);
  check('Browser makes zero direct provider requests', providerCalls.length === 0, `${providerCalls.length} provider request(s)`);
  const summary = await page.getByTestId('refresh-summary').innerText();
  check('Refresh summary shows jobs and companies checked', /12 jobs found · 6\/9 companies checked successfully/.test(summary), summary);
  const card = title => page.locator('div.bg-white.rounded-lg.border', { has: page.locator('h3', { hasText: title }) }).first();

  const cases = [
    ['Applied AI Engineer', 'Greenhouse', 'Anthropic'],
    ['Forward Deployed Software Engineer', 'Lever', 'Palantir'],
    ['Software Engineer, Frontend', 'Ashby', 'Ramp'],
  ];
  for (const [title, source, company] of cases) {
    await page.getByRole('link', { name: 'Jobs' }).click();
    await card(title).getByRole('button', { name: 'Tailor Resume' }).click();
    await page.waitForURL(/\/resume-ai/);
    const selected = page.getByTestId('selected-job');
    await selected.filter({ hasText: title }).waitFor();
    const text = await selected.innerText();
    const description = await page.getByTestId('job-description-preview').innerText();
    check(`${source} job -> Tailor Resume -> Resume AI receives Common Job`, text.includes(source) && text.includes(company) && description.length > 10,
      `${company} / ${source} / "${description.slice(0, 40)}…"`);
    await page.getByRole('button', { name: 'Analyze fit' }).click();
    await page.getByTestId('relevance').waitFor();
    check(`${source} job analyzed (same workflow)`, (await page.getByTestId('relevance').innerText()).includes('%'));
  }

  // 3. Tailor the Greenhouse job with the (fake) AI; validator blocks fabricated claims
  await page.getByRole('link', { name: 'Jobs' }).click();
  await card('Applied AI Engineer').getByRole('button', { name: 'Tailor Resume' }).click();
  await page.getByTestId('selected-job').filter({ hasText: 'Applied AI Engineer' }).waitFor();
  await page.getByRole('button', { name: 'Tailor Resume', exact: true }).click();
  await page.getByTestId('change-review').waitFor({ timeout: 20000 });
  const missing = await page.getByTestId('still-missing').innerText();
  check('Missing JD skill stays missing (GraphQL not added)', missing.includes('GraphQL'));
  await page.getByText(/Blocked by the truth validator/).click();
  const blocked = await page.getByTestId('blocked-changes').innerText();
  check('Unsupported AI claims blocked with reasons', blocked.includes('Unsupported skill "GraphQL"') && blocked.includes('Unsupported number/metric "40"'));

  // Edit with an unsupported claim -> warning, not silently accepted
  await page.getByRole('button', { name: 'Edit', exact: true }).click();
  await page.getByRole('textbox', { name: 'Updated line' }).fill('Built dashboards in Angular with GraphQL.');
  await page.getByRole('button', { name: 'Save', exact: true }).click();
  await page.getByTestId('edit-warnings').waitFor();
  check('User edit checked by server (flags unsupported GraphQL)', (await page.getByTestId('edit-warnings').innerText()).includes('GraphQL'));
  await page.getByRole('button', { name: 'Cancel' }).click();

  const firstUpdated = await page.getByTestId('change-updated').innerText();
  await page.getByRole('button', { name: 'Accept', exact: true }).click();
  await page.getByRole('button', { name: 'Next change' }).click();
  await page.getByRole('button', { name: 'Reject', exact: true }).click();
  const rejectedText = await page.getByTestId('change-updated').innerText();
  check('Preview shows accepted change only', (await page.getByTestId('resume-preview').innerText()).includes(firstUpdated)
    && !(await page.getByTestId('resume-preview').innerText()).includes(rejectedText));

  for (const tab of ['Keywords', 'Match Analysis', 'Original']) {
    await page.getByRole('tab', { name: new RegExp(`^${tab}`) }).click();
  }
  check('Keywords / Match Analysis / Original tabs render', await page.getByTestId('original-preview').isVisible());
  await page.getByRole('tab', { name: 'Match Analysis' }).click();
  check('Match analysis explains it is not an employer ATS score', (await page.getByTestId('match-analysis').innerText()).includes("not the employer's ATS score"));

  // 4. Chat operations
  const chat = async (message, expect) => {
    await page.getByLabel('Message').fill(message);
    await page.getByRole('button', { name: 'Send' }).click();
    await page.getByTestId('chat-log').filter({ hasText: expect }).waitFor({ timeout: 15000 });
    return true;
  };
  check('Chat: "What skills am I missing?"', await chat('What skills am I missing?', "I won't add these"));
  check('Chat: "Focus more on Kubernetes" refused (not verified)', await chat('Focus more on Kubernetes', "Kubernetes isn't in your verified profile"));
  check('Chat: "Why did you change this bullet?"', await chat('Why did you change this bullet?', 'Evidence:'));

  // 5. Generate DOCX (server applies accepted change only)
  await page.getByRole('button', { name: 'Generate DOCX' }).click();
  const [download] = await Promise.all([page.waitForEvent('download'), page.getByRole('button', { name: 'Download DOCX' }).click()]);
  const file = join(tmp, download.suggestedFilename());
  await download.saveAs(file);
  const docText = spawnSync(PY, ['-c', `import docx,sys; print("\\n".join(p.text for p in docx.Document(sys.argv[1]).paragraphs))`, file], { encoding: 'utf8' }).stdout;
  check('DOCX generated with accepted change, without rejected one', docText.includes(firstUpdated) && !docText.includes(rejectedText), download.suggestedFilename());

  // 6. Master Resume unchanged; persistence across reload; no secrets in the browser
  await page.getByRole('tab', { name: 'Career Profile' }).click();
  const profileText = await page.getByTestId('career-profile').innerText();
  check('Master Resume unchanged after tailoring/generation', profileText.includes('Built real-time rail operations dashboards in Angular used by 300+ dispatchers.') && !profileText.includes(firstUpdated));
  await page.reload();
  await page.getByTestId('resume-preview').filter({ hasText: 'Alex Rivera' }).waitFor();
  check('Profile + session persist across reload', await page.getByTestId('workflow-tabs').isVisible());
  const storage = await page.evaluate(() => JSON.stringify({ ...localStorage }));
  const statusJson = await page.evaluate(() => fetch('/api/ai/status').then(r => r.text()));
  check('API key never reaches the browser', !storage.includes(SECRET) && !statusJson.includes(SECRET) && !(await page.content()).includes(SECRET));

  await page.getByRole('link', { name: 'Applications' }).click();
  const apps = await page.getByTestId('applications-page').innerText();
  check('Applications lists the tailored resume version for the job', apps.includes('Applied AI Engineer') && apps.includes('v1') && apps.includes('Saved'));

  // 7. Jobs page after a fresh load: still one server-side refresh, failed companies listed, statuses kept
  await page.goto(`${base}/`);
  const fetchButton = page.getByRole('button', { name: /Fetch Latest Jobs/ });
  await fetchButton.waitFor({ timeout: 15000 });
  const again = [];
  page.on('request', r => { if (/greenhouse\.io|lever\.co|ashbyhq\.com|\/api\/jobs\/refresh/.test(r.url())) again.push(r.url()); });
  await fetchButton.click();
  await page.getByTestId('refresh-summary').waitFor();
  check('Reload + fetch: one refresh request, no provider requests', again.length === 1 && again[0].endsWith('/api/jobs/refresh'), again.join(', '));
  check('Failed companies still reported (partial failure)', (await page.locator('text=/Failed Companies \\(3\\)/').count()) === 1);

  // 8. Auth foundation (temporary /auth-dev page; the final UI comes later)
  const authNet = [];
  page.on('request', r => authNet.push(r.url()));
  await page.goto(`${base}/auth-dev`);
  const status = page.getByTestId('auth-status');
  await status.getByText('unauthenticated').waitFor();
  check('Auth: initial state from /api/auth/me is signed out', true);
  await page.getByLabel('Email').fill('e2e@example.com');
  await page.getByLabel('Password').fill('wrong-password');
  await page.getByRole('button', { name: 'Log in' }).click();
  await page.getByTestId('auth-message').getByText(/Incorrect email or password/).waitFor();
  check('Auth: invalid login shows the clean API error', true);
  await page.getByLabel('Password').fill('E2E-password-123');
  await page.getByRole('button', { name: 'Log in' }).click();
  await status.getByText('authenticated', { exact: true }).waitFor();
  check('Auth: login -> authenticated with name/email', (await status.innerText()).includes('E2E User <e2e@example.com>'));
  check('Auth: ProtectedRoute renders children when signed in', await page.getByTestId('protected-content').isVisible());
  const cookies = await context.cookies();
  const access = cookies.find(c => c.name === 'jr_access');
  const refresh = cookies.find(c => c.name === 'jr_refresh');
  check('Auth: session cookies are HttpOnly + SameSite=Lax, path-scoped',
    access?.httpOnly && refresh?.httpOnly && access.sameSite === 'Lax' && access.path === '/api' && refresh.path === '/api/auth',
    JSON.stringify(cookies.map(({ name, path, httpOnly, sameSite }) => ({ name, path, httpOnly, sameSite }))));
  const visible = await page.evaluate(() => ({ cookie: document.cookie, storage: JSON.stringify({ ...localStorage, ...sessionStorage }) }));
  check('Auth: tokens not readable by JS or stored in localStorage/sessionStorage',
    !visible.cookie.includes('jr_') && !/at_[0-9a-f]{16}|rt_[0-9a-f]{16}|access_token|refresh_token/.test(visible.storage + visible.cookie));
  await page.reload();
  await status.getByText('authenticated', { exact: true }).waitFor();
  check('Auth: session survives a reload (cookie sent automatically)', true);
  const regular = await page.evaluate(() => fetch('/api/health').then(r => r.status));
  check('Auth: /api/health stays public', regular === 200);
  await page.getByLabel('Name (sign up only)').fill('New Person');
  await page.getByLabel('Email').fill('new@example.com');
  await page.getByLabel('Password').fill('Another-pass-456');
  await page.getByRole('button', { name: 'Sign up' }).click();
  await page.getByTestId('auth-message').getByText(/Check your email/).waitFor();
  check('Auth: signup with email confirmation reports verification required', true);
  await page.getByRole('button', { name: 'Log out' }).click();
  await status.getByText('unauthenticated').waitFor();
  const after = (await context.cookies()).filter(c => c.name.startsWith('jr_'));
  check('Auth: logout clears the session cookies', after.length === 0, JSON.stringify(after.map(c => c.name)));
  await page.reload();
  await status.getByText('unauthenticated').waitFor();
  check('Auth: signed out after reload', true);
  const direct = authNet.filter(u => u.includes(`:${PORTS.supabase}`) || /supabase\.co/.test(u));
  check('Auth: browser never calls Supabase directly (only /api/auth)', direct.length === 0 && authNet.some(u => u.includes('/api/auth/login')), direct.join(', '));
  check('No page errors', errors.length === 0, errors.join(' | '));
  await browser.close();
}

main()
  .catch(error => { check('e2e run', false, error.stack || error.message); })
  .finally(() => {
    procs.forEach(p => p.kill());
    const failed = results.filter(r => !r.ok).length;
    console.log(`\n${results.length - failed}/${results.length} checks passed`);
    process.exit(failed ? 1 : 0);
  });
