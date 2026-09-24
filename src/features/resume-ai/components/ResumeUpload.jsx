import { useRef } from 'react';
import { FileUp, ShieldCheck } from 'lucide-react';
import { Button, Card } from './ui';

const MAX_BYTES = 10 * 1024 * 1024;

/** Master Resume upload (PDF/DOCX). The server parses it; AI structures it. */
export default function ResumeUpload({ masterResume, onUpload, aiConfigured, onOpenSettings, busy, compact = false }) {
  const input = useRef(null);

  const pick = event => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    if (!/\.(pdf|docx)$/i.test(file.name)) {
      alert('Unsupported file type. Please use a .pdf or .docx resume.');
      return;
    }
    if (file.size > MAX_BYTES) {
      alert('File is too large (max 10 MB).');
      return;
    }
    onUpload(file);
  };

  const control = (
    <>
      <input ref={input} type="file" accept=".pdf,.docx" hidden onChange={pick} data-testid="master-resume-input" />
      <Button variant={compact ? 'secondary' : 'primary'} onClick={() => input.current?.click()} disabled={!!busy || !aiConfigured}>
        <FileUp className="w-4 h-4" />
        {masterResume ? 'Replace Master Resume' : 'Upload Master Resume'}
      </Button>
    </>
  );

  if (compact) return control;

  return (
    <Card title="Master Resume" icon={FileUp}>
      <p className="text-sm text-slate-600">
        Upload your resume as a <strong>.pdf</strong> or <strong>.docx</strong> (max 10 MB). It becomes your
        <strong> Master Resume</strong>: the source of truth every tailored resume is built from. Tailoring never changes it.
      </p>
      <div className="flex items-center gap-2 mt-3 text-xs text-slate-500">
        <ShieldCheck className="w-4 h-4 text-emerald-600" />
        Facts are extracted as-is. Employer names, titles, dates and degrees are protected.
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-2">
        {control}
        {!aiConfigured && (
          <span className="text-xs text-slate-500">
            Resume extraction needs an AI provider.{' '}
            <button type="button" className="text-amber-600 hover:underline" onClick={onOpenSettings}>Open Settings →</button>
          </span>
        )}
      </div>
    </Card>
  );
}
