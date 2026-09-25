import { useRef, useState } from 'react';
import { Briefcase, ExternalLink, FileText, Info, Sparkles, Target } from 'lucide-react';
import { SOURCE_LABELS } from '../../../shared/models/commonJob';
import { adjustedAfterScore, isApplied } from '../logic';
import { Button, Card, Chip, Modal, inputClass } from './ui';

const MODES = [
  ['conservative', 'Conservative', 'fewest changes, required skills only'],
  ['balanced', 'Balanced', 'required + preferred skills'],
  ['strong', 'Strong', 'also strengthens the summary']
];

function Score({ label, value, accent }) {
  return (
    <div className="flex flex-col items-center">
      <span className={`text-2xl font-semibold ${accent ? 'text-amber-600' : 'text-slate-900'}`}>{value}%</span>
      <span className="text-xs text-slate-500">{label}</span>
    </div>
  );
}

/** Selected job + JD input + estimated relevance + generation. */
export default function JobMatchPanel({ state, actions, onGoToJobs }) {
  const { job, session, analysis, mode, profile, busy } = state;
  const [jdText, setJdText] = useState('');
  const [showPaste, setShowPaste] = useState(false);
  const [showAbout, setShowAbout] = useState(false);
  const [validateFormat, setValidateFormat] = useState(null);
  const fileInput = useRef(null);

  const applied = session ? session.changes.filter(isApplied) : [];
  const overrides = applied.filter(c => c.userFlagged?.length);
  const keywordsStrengthened = new Set(applied.flatMap(c => c.keywordsAdded || [])).size;
  const before = session?.matchBefore ?? analysis?.matchBefore;

  return (
    <Card
      title="Job Match"
      icon={Target}
      actions={(
        <button type="button" className="text-slate-400 hover:text-slate-600" aria-label="What is this score?" onClick={() => setShowAbout(true)}>
          <Info className="w-4 h-4" />
        </button>
      )}
    >
      {job ? (
        <div data-testid="selected-job">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <div className="text-sm font-semibold text-slate-900 truncate">{job.title || 'Job description'}</div>
              <div className="text-xs text-slate-500 flex flex-wrap gap-x-2">
                {job.company && <span>{job.company}</span>}
                {job.location && <span>{job.location}</span>}
              </div>
            </div>
            <Chip tone={job.source === 'manual' ? 'slate' : 'amber'}>{SOURCE_LABELS[job.source] || job.source}</Chip>
          </div>
          {job.applyUrl && (
            <a href={job.applyUrl} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 mt-1 text-xs text-amber-600 hover:underline">
              View posting <ExternalLink className="w-3 h-3" />
            </a>
          )}
          <p className="mt-2 text-xs text-slate-500 line-clamp-2" data-testid="job-description-preview">{job.description}</p>
        </div>
      ) : (
        <div className="text-sm text-slate-600">
          No job selected. Pick one in <button type="button" onClick={onGoToJobs} className="text-amber-600 hover:underline">Jobs</button> with
          <strong> Tailor Resume</strong>, or add an external job description below.
        </div>
      )}

      <div className="flex flex-wrap gap-2 mt-3">
        <Button onClick={() => setShowPaste(v => !v)}><FileText className="w-4 h-4" />Paste JD</Button>
        <input ref={fileInput} type="file" accept=".pdf,.docx,.txt" hidden onChange={e => {
          const file = e.target.files?.[0];
          e.target.value = '';
          if (file) actions.uploadJobDescription(file);
        }} />
        <Button onClick={() => fileInput.current?.click()} disabled={!!busy}>Upload JD</Button>
      </div>
      {showPaste && (
        <div className="mt-2">
          <textarea className={inputClass} rows={6} value={jdText} onChange={e => setJdText(e.target.value)}
            placeholder="Paste the full job description for an external job…" aria-label="Job description" />
          <div className="mt-2 flex justify-end">
            <Button variant="dark" disabled={!jdText.trim()} onClick={() => {
              actions.setManualJobDescription(jdText);
              setJdText('');
              setShowPaste(false);
            }}>Use this job description</Button>
          </div>
        </div>
      )}

      <div className="mt-4">
        <div className="text-xs font-medium text-slate-500 mb-1">Tailoring mode</div>
        <div className="grid grid-cols-3 gap-1">
          {MODES.map(([value, label, hint]) => (
            <button key={value} type="button" title={hint} onClick={() => actions.setMode(value)}
              className={`px-2 py-1.5 text-xs rounded-md transition-colors ${mode === value ? 'bg-amber-500 text-white' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}`}>
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex gap-2 mt-3">
        <Button className="flex-1" onClick={actions.analyze} disabled={!!busy || !job || !profile}>Analyze fit</Button>
        <Button variant="primary" className="flex-1" onClick={() => actions.tailor()} disabled={!!busy || !job || !profile}>
          <Sparkles className="w-4 h-4" />Tailor Resume
        </Button>
      </div>

      {before != null && (
        <div className="mt-4 pt-4 border-t border-slate-100">
          <div className="text-xs text-slate-500 text-center mb-2">Estimated Resume Relevance</div>
          <div className="flex justify-around" data-testid="relevance">
            <Score label="Before" value={before} />
            {session && <Score label="Proposed" value={session.matchAfter} />}
            {session && <Score label="Approved" value={adjustedAfterScore(session)} accent />}
          </div>
          <div className="mt-3 space-y-2 text-sm">
            <div>
              <div className="text-xs font-medium text-slate-500">Strong matches</div>
              <div className="flex flex-wrap gap-1 mt-1">
                {(session || analysis).strongMatches.length
                  ? (session || analysis).strongMatches.map(s => <Chip key={s} tone="green">✓ {s}</Chip>)
                  : <span className="text-xs text-slate-400">None yet</span>}
              </div>
            </div>
            <div>
              <div className="text-xs font-medium text-slate-500">Still missing (never added)</div>
              <div className="flex flex-wrap gap-1 mt-1" data-testid="still-missing">
                {(session || analysis).stillMissing.length
                  ? (session || analysis).stillMissing.map(m => <Chip key={m.skill} tone="red">{m.skill}</Chip>)
                  : <span className="text-xs text-slate-400">Nothing missing</span>}
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-2 mt-4 pt-4 border-t border-slate-100">
        <Button variant="dark" disabled={!!busy || !profile} onClick={() => setValidateFormat('docx')}><Briefcase className="w-4 h-4" />Generate DOCX</Button>
        <Button variant="primary" disabled={!!busy || !profile} onClick={() => setValidateFormat('pdf')}>Generate PDF</Button>
      </div>

      {showAbout && (
        <Modal title="About this score" onClose={() => setShowAbout(false)}
          footer={<Button variant="primary" onClick={() => setShowAbout(false)}>Got it</Button>}>
          This is an <strong>Estimated Resume Relevance</strong> score — not the employer's ATS score, which no outside tool can see,
          and not a prediction of an interview. It is built from required/preferred skill coverage, responsibility alignment,
          title/seniority alignment and evidence strength, all traceable to your verified profile. See Match Analysis for the breakdown.
        </Modal>
      )}

      {validateFormat && (
        <Modal title="Final Validation" onClose={() => setValidateFormat(null)} footer={(
          <>
            <Button onClick={() => setValidateFormat(null)}>Close</Button>
            <Button variant="primary" onClick={() => { actions.generate(validateFormat); setValidateFormat(null); }}>
              Download {validateFormat.toUpperCase()}
            </Button>
          </>
        )}>
          <ul className="space-y-1" data-testid="validation-list">
            <li>✓ {applied.length} line{applied.length === 1 ? '' : 's'} updated</li>
            <li>✓ {keywordsStrengthened} relevant keyword{keywordsStrengthened === 1 ? '' : 's'} strengthened</li>
            <li>✓ {session?.blockedChanges?.length || 0} unsupported suggestion(s) blocked by the server</li>
            {overrides.length > 0 && (
              <li className="text-red-700">⚠ {overrides.length} of your own edit(s) were saved despite validator warnings and will be included as written</li>
            )}
            <li>✓ Employer names, job titles, dates and education preserved</li>
            {session && <li>✓ Estimated relevance: {adjustedAfterScore(session)}%</li>}
          </ul>
          <p className="mt-3 text-xs text-slate-500">
            Only changes you accepted or edited are included; pending or rejected ones keep your original wording.
            The Master Resume is not modified.
          </p>
        </Modal>
      )}
    </Card>
  );
}
