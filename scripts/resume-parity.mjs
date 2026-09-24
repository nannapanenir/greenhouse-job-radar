#!/usr/bin/env node
/**
 * Resume AI parity check: standalone Resume Tailor (Node) vs Python port.
 *
 *   node scripts/resume-parity.mjs --reference /path/to/resume-tailor
 *
 * The reference repo is used read-only (it needs `npm install`). Its modules
 * run unmodified; only aiProvider is stubbed so a canned AI reply reaches
 * the real sanitizers. Compared on the same fixtures:
 *   extractJsonObject, profileExtractor.sanitizeProfile,
 *   tailorEngine.validateAndSanitize, mockData local engine (+adjusted score),
 *   resumeParser (PDF/DOCX text), docx/pdf generators (document text).
 * Intentional differences are listed separately and don't fail the run.
 * Exit 0 = parity, 1 = unexpected differences, 2 = setup error.
 */

import { spawnSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const FIX = join(ROOT, 'tests/backend/fixtures');
const refArg = process.argv.indexOf('--reference');
const REF = resolve(refArg > 0 ? process.argv[refArg + 1] : process.env.RESUME_TAILOR_REF || '../resume-tailor');
const PYTHON = process.env.PYTHON || 'python3';

function setupError(message) {
  console.error(`SETUP ERROR: ${message}`);
  process.exit(2);
}
if (!existsSync(join(REF, 'server/tailorEngine.js'))) setupError(`resume-tailor not found at ${REF} (use --reference)`);
if (!existsSync(join(REF, 'node_modules/docx'))) setupError(`run "npm install" in ${REF} first`);

const require = createRequire(join(REF, 'server/index.js'));
let cannedReply = '';
require.cache[require.resolve('./aiProvider')] = {
  id: 'aiProvider-stub', filename: 'aiProvider-stub', loaded: true, children: [], paths: [],
  exports: { callChatCompletionWithRetry: async () => cannedReply, callChatCompletion: async () => cannedReply },
};
const { extractJsonObject } = require('./extractJsonObject');
const { extractProfileFromResumeText } = require('./profileExtractor');
const { tailorWithAI } = require('./tailorEngine');
const { extractResumeText } = require('./resumeParser');
const { buildResumeDocx } = require('./docxGenerator');
const { buildResumePdf } = require('./pdfGenerator');
const mock = vm.runInNewContext(
  `${readFileSync(join(REF, 'public/js/mockData.js'), 'utf8')}
   ;({ buildSessionFromJD, computeAdjustedAfterScore })`, {});

const quiet = async (fn) => {
  const original = console.error;
  console.error = () => {};
  try { return { ok: true, value: JSON.parse(JSON.stringify(await fn())) }; }
  catch (e) { return { ok: false, error: e.message }; }
  finally { console.error = original; }
};

function python(requests) {
  const out = spawnSync(PYTHON, [join(ROOT, 'scripts/resume_parity_helper.py')], {
    input: JSON.stringify(requests), encoding: 'utf8', maxBuffer: 64 * 1024 * 1024,
  });
  if (out.status !== 0) setupError(`python helper failed:\n${out.stderr}`);
  return JSON.parse(out.stdout);
}

const results = { same: 0, different: [], intentional: [] };
function compare(label, node, py, intentional = null) {
  const a = JSON.stringify(node.ok ? node.value : { error: true });
  const b = JSON.stringify(py.ok ? py.value : { error: true });
  if (a === b) { results.same++; return; }
  const entry = `${label}\n      node:   ${a.slice(0, 400)}\n      python: ${b.slice(0, 400)}`;
  (intentional ? results.intentional : results.different).push(intentional ? `${label} — ${intentional}` : entry);
}
const words = (text) => String(text).replace(/[••]/g, ' ').split(/\s+/).filter(Boolean);

const profile = JSON.parse(readFileSync(join(FIX, 'profile.json'), 'utf8'));
const aiProfiles = JSON.parse(readFileSync(join(FIX, 'ai_profile_responses.json'), 'utf8'));
const aiTailor = readFileSync(join(FIX, 'ai_tailor_response.json'), 'utf8');
const jds = ['jd_frontend.txt', 'jd_backend.txt', 'jd_crlf.txt'].map((f) => [f, readFileSync(join(FIX, f), 'utf8')]);

// 1. extractJsonObject
const jsonCases = [...Object.values(aiProfiles), aiTailor, '<think>{"x":1}</think> {"y": 2}', '```\n{"z": [1, 2]}\n```'];
const pyJson = python(jsonCases.map((raw) => ({ op: 'extract_json', raw })));
for (const [i, raw] of jsonCases.entries()) {
  compare(`extractJsonObject #${i}`, await quiet(() => extractJsonObject(raw)), pyJson[i]);
}

// 2. profile extraction sanitizer
const pyProfiles = python(Object.values(aiProfiles).map((raw) => ({ op: 'sanitize_profile', raw })));
for (const [i, [name, raw]] of Object.entries(aiProfiles).entries()) {
  cannedReply = raw;
  const node = await quiet(() => extractProfileFromResumeText({ model: 'm', resumeText: 'x' }));
  compare(`sanitizeProfile(${name})`, node, pyProfiles[i],
    name === 'string_skills' ? 'Python keeps skills returned as plain strings; Node drops them' : null);
}

// 3. tailoring sanitizer (stage 1 = Node rules), then report what stage 2 blocks on top
cannedReply = aiTailor;
const nodeTailor = await quiet(() => tailorWithAI({ model: 'm', profile, jobDescriptionText: 'jd', mode: 'balanced' }));
const [pyStage1, pyStage2] = python([
  { op: 'tailor_sanitize', raw: aiTailor, profile, evidence: false },
  { op: 'tailor_sanitize', raw: aiTailor, profile, evidence: true },
]);
if (nodeTailor.ok) delete nodeTailor.value.source;
delete pyStage1.value.blocked;
compare('validateAndSanitize (same rules)', nodeTailor, pyStage1);
const evidenceBlocked = pyStage2.value.blocked.filter((b) => b.stage === 2);
results.intentional.push(`validateAndSanitize + evidence validator — ${evidenceBlocked.length} more change(s) blocked: `
  + evidenceBlocked.map((b) => b.reasons[0]).join(' | ')
  + `; strongMatches corrected ${JSON.stringify(nodeTailor.value.strongMatches)} -> ${JSON.stringify(pyStage2.value.strongMatches)}`);

// 4. local engine (all JDs x modes), same profile + variants that exercise documented fixes
const lowerProfile = JSON.parse(JSON.stringify(profile));
lowerProfile.skills = lowerProfile.skills.map((s) => ({ ...s, name: s.name === 'TypeScript' ? 'Typescript' : s.name }));
lowerProfile.experience[0].technologies = lowerProfile.experience[0].technologies.map((t) => (t === 'TypeScript' ? 'Typescript' : t));
const emptySummary = { ...JSON.parse(JSON.stringify(profile)), summary: { text: '', status: 'extracted' } };
const engineCases = [];
for (const [name, jd] of jds) {
  for (const mode of ['conservative', 'balanced', 'strong']) engineCases.push({ label: `${name}/${mode}`, jd, mode, profile });
}
engineCases.push({ label: 'jd_frontend.txt/balanced (profile says "Typescript")', jd: jds[0][1], mode: 'balanced', profile: lowerProfile,
  intentional: 'case-insensitive skill verification (Node treats "Typescript" as missing)' });
engineCases.push({ label: 'jd_frontend.txt/strong (empty summary)', jd: jds[0][1], mode: 'strong', profile: emptySummary,
  intentional: 'no summary change built from an empty summary (Node proposes ", specializing in …")' });
const pyEngine = python(engineCases.map((c) => ({ op: 'fallback', jd: c.jd, mode: c.mode, profile: c.profile })));
const pyEngineValidated = python(engineCases.map((c) => ({ op: 'fallback', jd: c.jd, mode: c.mode, profile: c.profile, evidence: true })));
engineCases.forEach((c, i) => {
  compare(`buildSessionFromJD ${c.label}`, { ok: true, value: mock.buildSessionFromJD(c.jd, c.profile, c.mode) }, pyEngine[i], c.intentional);
  const blocked = pyEngineValidated[i].value.blocked;
  if (blocked.length) results.intentional.push(`local engine ${c.label} — evidence validator blocked: ${blocked.map((b) => b.reasons[0]).join(' | ')}`);
});
const adjustedCases = [
  { matchBefore: 60, matchAfter: 80, changes: [{ status: 'accepted' }, { status: 'rejected' }, { status: 'edited' }] },
  { matchBefore: 41, matchAfter: 58, changes: [{ status: 'accepted' }, { status: 'pending' }] },
  { matchBefore: 50, matchAfter: 50, changes: [] },
];
const pyAdjusted = python(adjustedCases.map((session) => ({ op: 'adjusted', session })));
adjustedCases.forEach((s, i) => compare(`computeAdjustedAfterScore #${i}`, { ok: true, value: mock.computeAdjustedAfterScore(s) }, pyAdjusted[i]));

// 5. resume parsing (same files; compare the word sequence — layout whitespace differs by library)
// pdf-parse 1.1.1 (reference) fails its first PDF parse in a process ("bad XRef
// entry") and then works — warm it up so the comparison is about extraction.
await quiet(() => extractResumeText(readFileSync(join(FIX, 'sample_resume_pdfkit.pdf')), 'warmup.pdf'));
const parseCases = [
  ['sample_resume_pdfkit.pdf', null],
  ['sample_resume.docx', null],
  ['sample_resume.pdf', 'the reference parser (pdf-parse 1.1.1, old pdf.js) fails on ReportLab PDFs with "bad XRef entry" — including the PDFs Resume AI generates; PyMuPDF reads them'],
];
for (const [file, intentional] of parseCases) {
  const buffer = readFileSync(join(FIX, file));
  const name = file.replace('_pdfkit', '');
  const node = await quiet(async () => words(await extractResumeText(buffer, name)));
  const [py] = python([{ op: 'parse', filename: name, data: buffer.toString('base64') }]);
  compare(`extractResumeText(${file})`, node, { ok: py.ok, value: py.ok ? words(py.value) : null }, intentional);
}
const badPdf = Buffer.from('<html>not a pdf</html>');
const nodeBad = await quiet(() => extractResumeText(badPdf, 'x.pdf'));
const [pyBad] = python([{ op: 'parse', filename: 'x.pdf', data: badPdf.toString('base64') }]);
compare('extractResumeText(renamed HTML) rejected', { ok: true, value: nodeBad.ok }, { ok: true, value: pyBad.ok });

// 6. generators: same tailored profile -> document text (both extracted by the same Python readers)
for (const format of ['docx', 'pdf']) {
  const nodeFile = (format === 'pdf' ? await buildResumePdf(profile) : await buildResumeDocx(profile)).toString('base64');
  const [pyFile] = python([{ op: 'generate', profile, format }]);
  const [nodeText, pyText] = python([{ op: 'document_text', data: nodeFile, kind: format }, { op: 'document_text', data: pyFile.value, kind: format }]);
  compare(`generate ${format} (document text)`, { ok: true, value: words(nodeText.value) }, { ok: true, value: words(pyText.value) });
}

console.log(`Reference: ${REF}`);
console.log(`Identical: ${results.same} checks`);
if (results.intentional.length) {
  console.log(`\nIntentional differences (${results.intentional.length}):`);
  results.intentional.forEach((d) => console.log(`  - ${d}`));
}
if (results.different.length) {
  console.log(`\nPARITY FAILED - ${results.different.length} unexpected difference(s):`);
  results.different.forEach((d) => console.log(`  - ${d}`));
  process.exitCode = 1;
} else {
  console.log('\nPARITY OK - Python Resume AI matches the standalone Resume Tailor (apart from the intentional differences above).');
}
