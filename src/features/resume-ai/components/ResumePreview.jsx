import { Fragment, useState } from 'react';
import { changeForBullet, displayedText, isApplied, KNOWN_SKILLS, tailoredPreview } from '../logic';

function highlight(text, on) {
  if (!on || !text) return text;
  const skills = [...KNOWN_SKILLS].sort((a, b) => b.length - a.length).map(s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
  const parts = text.split(new RegExp(`\\b(${skills.join('|')})\\b`, 'gi'));
  return parts.map((part, i) => (i % 2 ? <mark key={i} className="bg-amber-100 text-slate-900 rounded px-0.5">{part}</mark> : <Fragment key={i}>{part}</Fragment>));
}

/** Resume preview: tailored (approved changes only) or the untouched Master Resume. */
export default function ResumePreview({ profile, session, original = false, compact = false }) {
  const [toggles, setToggles] = useState({ changes: true, keywords: false });
  const [openId, setOpenId] = useState(null);
  if (!profile) return null;
  const shown = original ? profile : tailoredPreview(profile, session);
  const p = shown.personalInformation || {};
  const contact = [p.email, p.phone, p.location, p.linkedIn].filter(Boolean).join(' • ');

  const line = (id, text) => {
    const change = !original && changeForBullet(session, id);
    const applied = change && isApplied(change);
    return (
      <li key={id} onClick={() => change && setOpenId(openId === id ? null : id)}
        className={`${applied && toggles.changes ? 'bg-emerald-50 border-l-2 border-emerald-400 pl-1' : ''} ${change ? 'cursor-pointer' : ''}`}>
        {highlight(text, toggles.keywords)}
        {openId === id && change && (
          <div className="mt-1 text-xs text-slate-500 bg-slate-50 rounded p-2">
            <strong>Original:</strong> {change.original}<br />
            <strong>Proposed:</strong> {displayedText(change)} ({change.status})<br />
            <strong>Why:</strong> {change.reason}
          </div>
        )}
      </li>
    );
  };

  const summaryChange = !original && changeForBullet(session, 'summary');

  return (
    <div>
      {!original && !compact && (
        <div className="flex flex-wrap gap-4 mb-3 text-xs text-slate-600">
          <label className="flex items-center gap-1"><input type="checkbox" checked={toggles.changes} onChange={e => setToggles({ ...toggles, changes: e.target.checked })} />Highlight changed lines</label>
          <label className="flex items-center gap-1"><input type="checkbox" checked={toggles.keywords} onChange={e => setToggles({ ...toggles, keywords: e.target.checked })} />Highlight keywords</label>
        </div>
      )}
      <article className="bg-white border border-slate-200 rounded-md p-5 text-sm text-slate-800 space-y-3" data-testid={original ? 'original-preview' : 'resume-preview'}>
        <header>
          <h2 className="text-xl font-semibold text-slate-900">{p.fullName || 'Your name'}</h2>
          {contact && <div className="text-xs text-slate-500">{contact}</div>}
        </header>
        {shown.summary?.text && (
          <section>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Summary</h3>
            <p className={summaryChange && isApplied(summaryChange) && toggles.changes ? 'bg-emerald-50 border-l-2 border-emerald-400 pl-1' : ''}>
              {highlight(shown.summary.text, toggles.keywords)}
            </p>
          </section>
        )}
        {shown.skills?.length > 0 && (
          <section>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Skills</h3>
            <p>{shown.skills.map(s => s.name).join(', ')}</p>
          </section>
        )}
        {shown.experience?.length > 0 && (
          <section>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Experience</h3>
            {shown.experience.map(exp => (
              <div key={exp.id} className="mt-2">
                <div><strong>{exp.title}</strong> — {exp.company}</div>
                <div className="text-xs text-slate-500">{exp.startDate} – {exp.endDate}{exp.location ? ` • ${exp.location}` : ''}</div>
                <ul className="list-disc ml-5 mt-1 space-y-1">{exp.bullets.map(b => line(b.id, b.text))}</ul>
              </div>
            ))}
          </section>
        )}
        {shown.education?.length > 0 && (
          <section>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Education</h3>
            {shown.education.map(e => <div key={e.id}>{e.degree}, {e.institution}{e.endDate ? ` (${e.endDate})` : ''}</div>)}
          </section>
        )}
        {shown.certifications?.length > 0 && (
          <section>
            <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Certifications</h3>
            {shown.certifications.map(c => <div key={c.id}>{[c.name, c.issuer, c.year].filter(Boolean).join(' — ')}</div>)}
          </section>
        )}
      </article>
    </div>
  );
}
