import { adjustedAfterScore, coverage, isApplied } from '../logic';

const SENIORITY = ['senior', 'lead', 'staff', 'principal'];

function Tile({ label, value, sub, highlight }) {
  return (
    <div className={`rounded-lg border p-3 ${highlight ? 'border-amber-200 bg-amber-50' : 'border-slate-200 bg-white'}`}>
      <div className="text-xs text-slate-500">{label}</div>
      <div className="text-lg font-semibold text-slate-900">{value}</div>
      {sub && <div className="text-xs text-slate-500">{sub}</div>}
    </div>
  );
}

/** Match Analysis: Estimated Resume Relevance breakdown (not an employer ATS score). */
export default function MatchAnalysis({ session, profile }) {
  const required = coverage(session.keywords, 'required');
  const preferred = coverage(session.keywords, 'preferred');
  const applied = session.changes.filter(isApplied);
  const responsibility = session.changes.length ? Math.round((applied.length / session.changes.length) * 100) : 0;
  const jdLevel = SENIORITY.find(w => (session.jobTitle || '').toLowerCase().includes(w));
  const hasLevel = (profile?.experience || []).some(e => SENIORITY.some(w => (e.title || '').toLowerCase().includes(w)));
  const pct = v => (v === null ? '—' : `${v}%`);

  return (
    <div data-testid="match-analysis">
      <p className="text-xs text-slate-500 mb-3">
        Estimated Resume Relevance — an explainable estimate from your verified profile. It is not the employer's ATS score
        and does not predict whether you'll be interviewed.
      </p>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
        <Tile label="Before" value={`${session.matchBefore}%`} />
        <Tile label="After (approved changes)" value={`${adjustedAfterScore(session)}%`} highlight />
        <Tile label="Required skill coverage" value={pct(required.pct)} sub={`${required.matched}/${required.total} verified`} />
        <Tile label="Preferred skill coverage" value={pct(preferred.pct)} sub={`${preferred.matched}/${preferred.total} verified`} />
        <Tile label="Responsibility alignment" value={`${responsibility}%`} sub={`${applied.length}/${session.changes.length} changes approved`} />
        <Tile label="Role / seniority" value={jdLevel && !hasLevel ? 'Review needed' : 'Aligned'}
          sub={jdLevel ? `Title implies “${jdLevel}” level` : 'No explicit seniority signal'} />
        <Tile label="Evidence strength" value={`${session.changes.length} backed`} sub="Every shown change cites profile evidence" />
        <Tile label="Blocked claims" value={session.blockedChanges?.length || 0} sub="Rejected by the server's truth validator" />
      </div>
      {session.corrections?.length > 0 && (
        <div className="mt-3 text-xs text-slate-600">
          <div className="font-medium text-slate-700">Validator corrections</div>
          <ul className="list-disc ml-4">{session.corrections.map(c => <li key={c}>{c}</li>)}</ul>
        </div>
      )}
      <div className="mt-3">
        <div className="text-sm font-medium text-slate-700">Remaining gaps</div>
        {session.stillMissing.length === 0
          ? <p className="text-sm text-slate-500">No remaining gaps — every extracted requirement is verified in your profile.</p>
          : <ul className="text-sm list-disc ml-5">{session.stillMissing.map(g => <li key={g.skill}><strong>{g.skill}</strong> — {g.note}</li>)}</ul>}
      </div>
    </div>
  );
}
