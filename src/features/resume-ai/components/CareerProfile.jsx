import { useState } from 'react';
import { Lock, Plus, UserRound, X } from 'lucide-react';
import { extractSkillsFromText } from '../logic';
import { Button, Card, Chip, Modal, inputClass } from './ui';

const STATUS = { extracted: ['Extracted', 'slate'], 'user-confirmed': ['Confirmed', 'green'], 'user-added': ['User-added', 'sky'], unverified: ['Unverified', 'amber'] };

function Tag({ status }) {
  const [label, tone] = STATUS[status] || [status, 'slate'];
  return <Chip tone={tone}>{label}</Chip>;
}

function FieldsModal({ title, warning, fields, onSave, onClose, confirmLabel = 'Save' }) {
  const [values, setValues] = useState(() => Object.fromEntries(fields.map(f => [f.key, f.value || ''])));
  const required = fields.filter(f => f.required);
  return (
    <Modal title={title} onClose={onClose} footer={(
      <>
        <Button onClick={onClose}>Cancel</Button>
        <Button variant="primary" disabled={required.some(f => !values[f.key].trim())}
          onClick={() => { onSave(Object.fromEntries(Object.entries(values).map(([k, v]) => [k, v.trim()]))); onClose(); }}>
          {confirmLabel}
        </Button>
      </>
    )}>
      {warning && <p className="mb-3 p-2 text-xs bg-amber-50 border border-amber-200 rounded-md text-amber-800">🔒 {warning}</p>}
      <div className="space-y-2">
        {fields.map(f => (
          <label key={f.key} className="block">
            <span className="text-xs font-medium text-slate-500">{f.label}</span>
            {f.multiline
              ? <textarea className={inputClass} rows={4} value={values[f.key]} onChange={e => setValues({ ...values, [f.key]: e.target.value })} />
              : <input className={inputClass} value={values[f.key]} placeholder={f.placeholder} onChange={e => setValues({ ...values, [f.key]: e.target.value })} />}
          </label>
        ))}
      </div>
    </Modal>
  );
}

function InlineAdd({ placeholder, onAdd }) {
  const [value, setValue] = useState('');
  return (
    <form className="flex gap-2 mt-2" onSubmit={e => { e.preventDefault(); if (value.trim()) { onAdd(value.trim()); setValue(''); } }}>
      <input className={inputClass} value={value} onChange={e => setValue(e.target.value)} placeholder={placeholder} />
      <Button type="submit"><Plus className="w-4 h-4" />Add</Button>
    </form>
  );
}

/** Career Profile = the Master Resume's verified facts. Only explicit user edits change it. */
export default function CareerProfile({ profile, masterResume, onUpdate, uploadControl }) {
  const [modal, setModal] = useState(null);
  const update = fn => onUpdate(p => { fn(p); return p; });
  const close = () => setModal(null);

  if (!profile) {
    return <Card title="Career Profile" icon={UserRound}><p className="text-sm text-slate-500">No career profile yet — upload your Master Resume first.</p><div className="mt-3">{uploadControl}</div></Card>;
  }
  const p = profile;
  const pi = p.personalInformation;

  return (
    <div className="space-y-4" data-testid="career-profile">
      <Card title="Master Resume" icon={Lock} actions={uploadControl}>
        {masterResume ? (
          <div className="text-xs text-slate-600 grid grid-cols-2 gap-1">
            <span>File: <strong>{masterResume.filename}</strong></span>
            <span>Type: {masterResume.fileType?.toUpperCase()}{masterResume.pageCount ? ` • ${masterResume.pageCount} page(s)` : ''}</span>
            <span>Uploaded: {new Date(masterResume.uploadedAt).toLocaleString()}</span>
            <span title={masterResume.sha256}>Fingerprint: {masterResume.sha256?.slice(0, 12)}…</span>
          </div>
        ) : <p className="text-xs text-slate-500">Profile entered manually.</p>}
        <p className="mt-2 text-xs text-slate-500">Tailored resumes are always derived from this profile; tailoring never overwrites it. Editing it here affects future tailoring only.</p>
      </Card>

      <Card title="Personal Information" actions={<Button variant="ghost" onClick={() => setModal({
        title: 'Edit personal information',
        fields: [['fullName', 'Full name'], ['email', 'Email'], ['phone', 'Phone'], ['location', 'Location'], ['linkedIn', 'LinkedIn'], ['portfolio', 'Portfolio']]
          .map(([key, label]) => ({ key, label, value: pi[key] })),
        onSave: v => update(x => { Object.assign(x.personalInformation, v); })
      })}>Edit</Button>}>
        <div className="text-sm"><strong>{pi.fullName || '—'}</strong></div>
        <div className="text-xs text-slate-600">{[pi.email, pi.phone, pi.location, pi.linkedIn, pi.portfolio].filter(Boolean).join(' • ') || '—'}</div>
      </Card>

      <Card title="Summary" actions={<Button variant="ghost" onClick={() => setModal({
        title: 'Edit summary', fields: [{ key: 'text', label: 'Summary', value: p.summary.text, multiline: true }],
        onSave: v => update(x => { x.summary = { text: v.text, status: 'user-confirmed' }; })
      })}>Edit</Button>}>
        <div className="flex items-start gap-2"><p className="text-sm text-slate-700 flex-1">{p.summary.text || '—'}</p><Tag status={p.summary.status} /></div>
      </Card>

      <Card title="Skills" actions={<Button variant="ghost" onClick={() => setModal({
        title: 'Add career information', fields: [{ key: 'text', label: 'Describe experience or skills you have verified', multiline: true, required: true }],
        confirmLabel: 'Add to profile',
        onSave: v => update(x => {
          const have = new Set(x.skills.map(s => s.name.toLowerCase()));
          extractSkillsFromText(v.text).filter(s => !have.has(s.toLowerCase())).forEach(s => x.skills.push({ name: s, status: 'user-added' }));
        })
      })}>Add career info</Button>}>
        <div className="flex flex-wrap gap-1">
          {p.skills.map((s, i) => (
            <span key={`${s.name}-${i}`} className="inline-flex items-center gap-1 px-2 py-0.5 text-xs bg-slate-100 text-slate-700 rounded-full">
              {s.name}{s.status === 'user-added' && <span className="text-sky-600">•</span>}
              <button type="button" aria-label={`Remove ${s.name}`} onClick={() => update(x => { x.skills.splice(i, 1); })}><X className="w-3 h-3" /></button>
            </span>
          ))}
        </div>
        <InlineAdd placeholder="Add a skill you have verified experience with" onAdd={v => update(x => { x.skills.push({ name: v, status: 'user-added' }); })} />
      </Card>

      <Card title="Experience" actions={<Button variant="ghost" disabled={!p.experience.length} onClick={() => setModal({
        title: 'Add project', fields: [
          { key: 'name', label: 'Project name', required: true }, { key: 'description', label: 'Description', multiline: true },
          { key: 'technologies', label: 'Technologies (comma separated)' },
          { key: 'experience', label: `Attach to role (${p.experience.map((e, i) => `${i + 1}=${e.company}`).join(', ')})`, value: '1' }],
        onSave: v => update(x => {
          const exp = x.experience[Math.max(0, Math.min(x.experience.length - 1, Number(v.experience) - 1 || 0))];
          const tech = v.technologies.split(',').map(t => t.trim()).filter(Boolean);
          exp.projects = [...(exp.projects || []), { name: v.name, description: v.description, technologies: tech, status: 'user-added' }];
          const have = new Set(x.skills.map(s => s.name.toLowerCase()));
          tech.filter(t => !have.has(t.toLowerCase())).forEach(t => x.skills.push({ name: t, status: 'user-added' }));
        })
      })}>Add project</Button>}>
        <div className="space-y-4">
          {p.experience.map((exp, ei) => (
            <div key={exp.id} className="border-b border-slate-100 pb-3 last:border-0">
              <div className="flex items-start justify-between gap-2">
                <div className="text-sm">
                  <Lock className="inline w-3 h-3 text-slate-400 mr-1" /><strong>{exp.title}</strong> — {exp.company}
                  <div className="text-xs text-slate-500">{exp.startDate} – {exp.endDate}{exp.location ? ` • ${exp.location}` : ''}</div>
                </div>
                <div className="flex items-center gap-1"><Tag status={exp.status} />
                  <Button variant="ghost" onClick={() => setModal({
                    title: `Edit ${exp.company}`,
                    warning: 'Company, job title and dates are protected facts. Only change them if the extracted data was wrong.',
                    confirmLabel: 'Save (I confirm this is accurate)',
                    fields: [['company', 'Company'], ['title', 'Job title'], ['startDate', 'Start date'], ['endDate', 'End date'], ['location', 'Location']]
                      .map(([key, label]) => ({ key, label, value: exp[key], required: key === 'company' })),
                    onSave: v => update(x => { Object.assign(x.experience[ei], v, { status: 'user-confirmed' }); })
                  })}>Edit</Button>
                </div>
              </div>
              <div className="flex flex-wrap gap-1 mt-1">
                {exp.technologies.map((t, ti) => (
                  <span key={`${t}-${ti}`} className="inline-flex items-center gap-1 px-2 py-0.5 text-xs bg-emerald-50 text-emerald-700 rounded-full">{t}
                    <button type="button" aria-label={`Remove ${t}`} onClick={() => update(x => { x.experience[ei].technologies.splice(ti, 1); })}><X className="w-3 h-3" /></button>
                  </span>
                ))}
              </div>
              <ul className="list-disc ml-5 mt-2 space-y-1 text-sm">
                {exp.bullets.map((b, bi) => (
                  <li key={b.id}>{b.text} <Tag status={b.status} />
                    <button type="button" aria-label="Remove bullet" className="ml-1 text-slate-400 hover:text-red-600" onClick={() => update(x => { x.experience[ei].bullets.splice(bi, 1); })}><X className="inline w-3 h-3" /></button>
                  </li>
                ))}
              </ul>
              {(exp.projects || []).map(pr => <div key={pr.name} className="text-xs text-slate-600 mt-1">Project: <strong>{pr.name}</strong> {pr.technologies?.length ? `(${pr.technologies.join(', ')})` : ''}</div>)}
              <InlineAdd placeholder="Add a verified accomplishment for this role"
                onAdd={v => update(x => { x.experience[ei].bullets.push({ id: `user-${Date.now()}`, text: v, status: 'user-added' }); })} />
            </div>
          ))}
          {!p.experience.length && <p className="text-sm text-slate-500">No experience on file.</p>}
        </div>
      </Card>

      <div className="grid md:grid-cols-2 gap-4">
        <Card title="Education" actions={<Button variant="ghost" onClick={() => setModal({
          title: 'Add education', fields: [{ key: 'degree', label: 'Degree', required: true }, { key: 'institution', label: 'Institution', required: true }, { key: 'endDate', label: 'End year' }],
          onSave: v => update(x => { x.education.push({ id: `edu-${Date.now()}`, ...v, status: 'user-added' }); })
        })}>Add</Button>}>
          {p.education.length ? p.education.map((e, i) => (
            <div key={e.id} className="text-sm flex items-center gap-2"><Lock className="w-3 h-3 text-slate-400" />{e.degree}, {e.institution}{e.endDate ? ` (${e.endDate})` : ''}
              <button type="button" aria-label="Remove education" className="text-slate-400 hover:text-red-600" onClick={() => window.confirm(`Delete ${e.degree}?`) && update(x => { x.education.splice(i, 1); })}><X className="w-3 h-3" /></button>
            </div>)) : <p className="text-sm text-slate-500">None on file.</p>}
        </Card>
        <Card title="Certifications" actions={<Button variant="ghost" onClick={() => setModal({
          title: 'Add certification', fields: [{ key: 'name', label: 'Certification', required: true }, { key: 'issuer', label: 'Issuer' }, { key: 'year', label: 'Year' }],
          onSave: v => update(x => { x.certifications.push({ id: `cert-${Date.now()}`, ...v, status: 'user-added' }); })
        })}>Add</Button>}>
          {p.certifications.length ? p.certifications.map((c, i) => (
            <div key={c.id} className="text-sm flex items-center gap-2"><Lock className="w-3 h-3 text-slate-400" />{[c.name, c.issuer, c.year].filter(Boolean).join(' — ')}
              <button type="button" aria-label="Remove certification" className="text-slate-400 hover:text-red-600" onClick={() => window.confirm(`Delete ${c.name}?`) && update(x => { x.certifications.splice(i, 1); })}><X className="w-3 h-3" /></button>
            </div>)) : <p className="text-sm text-slate-500">None on file.</p>}
        </Card>
      </div>

      {modal && <FieldsModal {...modal} onClose={close} />}
    </div>
  );
}
