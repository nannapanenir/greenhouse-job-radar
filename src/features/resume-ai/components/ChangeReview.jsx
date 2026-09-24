import { useState } from 'react';
import { ArrowRight, Check, ChevronLeft, ChevronRight, Pencil, ShieldAlert, X } from 'lucide-react';
import { changeLabel, displayedText } from '../logic';
import { Button, Chip, Modal, STATUS_TONES, inputClass } from './ui';

const STATUS_LABEL = { pending: 'Pending review', accepted: '✓ Accepted', edited: '✎ Edited', rejected: '✕ Rejected' };

function EditModal({ change, onClose, onCheck, onSave }) {
  const [text, setText] = useState(displayedText(change));
  const [reasons, setReasons] = useState(null);
  const [checking, setChecking] = useState(false);

  const check = async () => {
    if (!text.trim()) return;
    setChecking(true);
    try {
      const found = await onCheck(change, text.trim());
      if (found.length) setReasons(found);
      else { onSave(change, text.trim()); onClose(); }
    } catch (error) {
      setReasons([`Could not validate this edit: ${error.message}`]);
    } finally {
      setChecking(false);
    }
  };

  return (
    <Modal title="Edit updated line" onClose={onClose} footer={(
      <>
        <Button onClick={onClose}>Cancel</Button>
        {reasons && <Button variant="reject" onClick={() => { onSave(change, text.trim(), reasons); onClose(); }}>Save anyway (flagged)</Button>}
        <Button variant="primary" disabled={!text.trim() || checking} onClick={check}>{checking ? 'Checking…' : 'Save'}</Button>
      </>
    )}>
      <textarea className={inputClass} rows={5} value={text} onChange={e => { setText(e.target.value); setReasons(null); }} aria-label="Updated line" />
      <p className="mt-2 text-xs text-slate-500">Employer names, titles and dates are protected facts. Your edit is checked against your verified profile before it's saved.</p>
      {reasons && (
        <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-md text-xs text-red-700" data-testid="edit-warnings">
          <div className="font-medium mb-1">This edit adds claims your profile doesn't support:</div>
          <ul className="list-disc ml-4">{reasons.map(r => <li key={r}>{r}</li>)}</ul>
          <div className="mt-1">Only save it if it is true — and consider adding the evidence to your Career Profile.</div>
        </div>
      )}
    </Modal>
  );
}

/** Changes tab: original vs updated, reason + evidence, Accept / Edit / Reject. */
export default function ChangeReview({ session, activeIndex, actions }) {
  const [editing, setEditing] = useState(null);
  const [showBlocked, setShowBlocked] = useState(false);
  const blocked = session.blockedChanges || [];

  const blockedPanel = blocked.length > 0 && (
    <div className="mt-4 pt-3 border-t border-slate-100">
      <button type="button" onClick={() => setShowBlocked(v => !v)} className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-700">
        <ShieldAlert className="w-4 h-4 text-red-500" /> Blocked by the truth validator ({blocked.length}) — {showBlocked ? 'hide' : 'show'}
      </button>
      {showBlocked && (
        <ul className="mt-2 space-y-2" data-testid="blocked-changes">
          {blocked.map((b, i) => (
            <li key={i} className="text-xs bg-red-50 border border-red-100 rounded-md p-2">
              <div className="text-slate-700">{b.updated || '(empty)'}</div>
              <ul className="list-disc ml-4 mt-1 text-red-700">{b.reasons.map(r => <li key={r}>{r}</li>)}</ul>
            </li>
          ))}
        </ul>
      )}
    </div>
  );

  if (!session.changes.length) {
    return (
      <div>
        <p className="text-sm text-slate-500">No proposed changes for this job — your resume already reflects your verified experience, or there wasn't enough truthful evidence to strengthen anything further.</p>
        {blockedPanel}
      </div>
    );
  }

  const index = Math.min(activeIndex, session.changes.length - 1);
  const change = session.changes[index];
  const total = session.changes.length;
  const acceptedCount = session.changes.filter(c => c.status === 'accepted' || c.status === 'edited').length;

  return (
    <div data-testid="change-review">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-slate-800">{changeLabel(change)}</h3>
          <Chip tone={STATUS_TONES[change.status]}>{STATUS_LABEL[change.status]}</Chip>
        </div>
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <span>{index + 1} of {total} • {acceptedCount} accepted</span>
          <Button variant="ghost" disabled={index === 0} onClick={() => actions.setActiveChangeIndex(index - 1)} aria-label="Previous change"><ChevronLeft className="w-4 h-4" /></Button>
          <Button variant="ghost" disabled={index === total - 1} onClick={() => actions.setActiveChangeIndex(index + 1)} aria-label="Next change"><ChevronRight className="w-4 h-4" /></Button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-[1fr_auto_1fr] gap-2 items-stretch mt-3">
        <div>
          <div className="text-xs font-medium text-slate-500 mb-1">Original</div>
          <div className="p-3 text-sm bg-slate-50 border border-slate-200 rounded-md h-full" data-testid="change-original">{change.original}</div>
        </div>
        <ArrowRight className="hidden md:block w-4 h-4 text-slate-400 self-center" />
        <div>
          <div className="text-xs font-medium text-slate-500 mb-1">Proposed</div>
          <div className="p-3 text-sm bg-amber-50 border border-amber-200 rounded-md h-full" data-testid="change-updated">{displayedText(change)}</div>
        </div>
      </div>

      {(change.keywordsAdded?.length > 0 || change.keywordsRemoved?.length > 0) && (
        <div className="flex flex-wrap gap-1 mt-3">
          {change.keywordsAdded.map(k => <Chip key={k} tone="green">{k} ✓</Chip>)}
          {change.keywordsRemoved.map(k => <Chip key={k} tone="red">{k} ✕</Chip>)}
        </div>
      )}

      <div className="mt-3 text-sm space-y-1">
        <div><span className="text-xs font-medium text-slate-500">Reason: </span>{change.reason || '—'}</div>
        <div><span className="text-xs font-medium text-slate-500">Evidence: </span><span className="text-slate-600">{change.evidence || '—'}</span></div>
        {change.userFlagged && (
          <div className="text-xs text-red-700">⚠ Your edit was saved with warnings: {change.userFlagged.join(' ')}</div>
        )}
      </div>

      <div className="flex flex-wrap gap-2 mt-4">
        <Button variant="accept" onClick={() => actions.accept(change)}><Check className="w-4 h-4" />Accept</Button>
        <Button onClick={() => setEditing(change)}><Pencil className="w-4 h-4" />Edit</Button>
        <Button variant="reject" onClick={() => actions.reject(change)}><X className="w-4 h-4" />Reject</Button>
        <span className="flex-1" />
        <Button variant="ghost" onClick={() => actions.restore(change)}>Restore proposed</Button>
        <Button variant="ghost" onClick={() => actions.regenerate(change)}>Regenerate</Button>
        <Button variant="primary" onClick={actions.acceptAllSafe}>Accept All Safe Changes</Button>
      </div>

      {blockedPanel}
      {editing && <EditModal change={editing} onClose={() => setEditing(null)} onCheck={actions.checkText} onSave={actions.saveEdit} />}
    </div>
  );
}
