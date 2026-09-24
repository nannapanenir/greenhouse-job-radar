import { Fragment, useState } from 'react';
import { displayedText, isApplied } from '../logic';
import { Chip } from './ui';

const STATUS_TONE = { Verified: 'green', Unverified: 'amber', 'Not found': 'red' };

function effectiveAfter(session, row) {
  const owning = session.changes.filter(c => (c.keywordsAdded || []).some(k => k.toLowerCase() === row.keyword.toLowerCase()));
  if (!owning.length) return row.after;
  return owning.some(isApplied) ? row.after : row.before;
}

/** Keywords tab: JD keywords, importance, before/after, verification. */
export default function KeywordsTab({ session }) {
  const [open, setOpen] = useState(null);
  if (!session.keywords.length) return <p className="text-sm text-slate-500">No keywords were extracted from this job description.</p>;

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm" data-testid="keywords-table">
        <thead>
          <tr className="text-left text-xs text-slate-500 border-b border-slate-100">
            <th className="py-2 pr-3">Keyword</th><th className="pr-3">Importance</th><th className="pr-3">Before</th>
            <th className="pr-3">After</th><th className="pr-3">Resume location</th><th>Verification</th>
          </tr>
        </thead>
        <tbody>
          {session.keywords.map(row => {
            const related = session.changes.filter(c =>
              (c.keywordsAdded || []).some(k => k.toLowerCase() === row.keyword.toLowerCase())
              || c.original.toLowerCase().includes(row.keyword.toLowerCase())
              || displayedText(c).toLowerCase().includes(row.keyword.toLowerCase()));
            return (
              <Fragment key={row.keyword}>
                <tr className="border-b border-slate-50 cursor-pointer hover:bg-slate-50" onClick={() => setOpen(open === row.keyword ? null : row.keyword)}>
                  <td className="py-2 pr-3 font-medium text-slate-800">{row.keyword}</td>
                  <td className="pr-3"><Chip tone={row.importance === 'Required' ? 'amber' : 'sky'}>{row.importance}</Chip></td>
                  <td className="pr-3">{row.before}</td>
                  <td className="pr-3">{effectiveAfter(session, row)}</td>
                  <td className="pr-3 text-slate-600">{row.location}</td>
                  <td><Chip tone={STATUS_TONE[row.status]}>{row.status}</Chip></td>
                </tr>
                {open === row.keyword && (
                  <tr>
                    <td colSpan={6} className="py-2 px-2 text-xs text-slate-600 bg-slate-50">
                      {related.length
                        ? <ul className="list-disc ml-4">{related.map(c => <li key={c.id}>{c.section}{c.company ? ` — ${c.company}` : ''}: “{displayedText(c)}”</li>)}</ul>
                        : `Not in the resume. ${row.status === 'Not found' ? 'No verified profile entry supports adding it truthfully.' : ''}`}
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
