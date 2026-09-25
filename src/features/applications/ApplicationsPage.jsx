import { useEffect, useState } from 'react';
import { ExternalLink, FileText } from 'lucide-react';
import { SOURCE_LABELS } from '../../shared/models/commonJob';
import { loadHistory } from '../resume-ai/services/resumeStore';

const STATUS_KEY = 'aiJobRadar_jobStatuses';

function readStatuses() {
  try {
    return JSON.parse(localStorage.getItem(STATUS_KEY) || '{}');
  } catch {
    return {};
  }
}

/**
 * Minimal Applications view: which tailored resume version was generated for
 * which job, next to the existing Job Radar status (keyed by apply URL).
 * Groundwork for application tracking — not a full tracker.
 */
export default function ApplicationsPage({ active }) {
  const [history, setHistory] = useState(loadHistory);
  const [statuses, setStatuses] = useState(readStatuses);

  useEffect(() => {
    if (active) {
      setHistory(loadHistory());
      setStatuses(readStatuses());
    }
  }, [active]);

  return (
    <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6" data-testid="applications-page">
      <div className="bg-white rounded-lg border border-slate-200">
        <div className="px-4 py-3 border-b border-slate-100 flex items-center gap-2">
          <FileText className="w-4 h-4 text-slate-500" />
          <h1 className="text-sm font-medium text-slate-700">Applications & tailored resumes</h1>
        </div>
        {history.length === 0 ? (
          <p className="p-4 text-sm text-slate-500">No tailored resumes yet. Use <strong>Tailor Resume</strong> on a job, then generate a DOCX or PDF.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-slate-500 border-b border-slate-100">
                  <th className="px-4 py-2">Job</th><th className="pr-3">Source</th><th className="pr-3">Resume version</th>
                  <th className="pr-3">Relevance</th><th className="pr-3">Generated</th><th className="pr-4">Job status</th>
                </tr>
              </thead>
              <tbody>
                {history.map(h => (
                  <tr key={h.id} className="border-b border-slate-50">
                    <td className="px-4 py-2">
                      <div className="font-medium text-slate-800">{h.title}</div>
                      <div className="text-xs text-slate-500">{h.company}
                        {h.applyUrl && <a href={h.applyUrl} target="_blank" rel="noopener noreferrer" className="ml-2 inline-flex items-center gap-0.5 text-amber-600 hover:underline">posting <ExternalLink className="w-3 h-3" /></a>}
                      </div>
                    </td>
                    <td className="pr-3">{SOURCE_LABELS[h.source] || h.source}</td>
                    <td className="pr-3">v{h.resumeVersion} • {h.format.toUpperCase()} • {h.appliedChangeIds.length} change(s)<div className="text-xs text-slate-400">{h.filename}</div></td>
                    <td className="pr-3">{h.matchBefore}% → {h.matchAfter}%</td>
                    <td className="pr-3 text-xs text-slate-500">{new Date(h.createdAt).toLocaleString()}</td>
                    <td className="pr-4">{(h.applyUrl && statuses[h.applyUrl]) || 'New'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </main>
  );
}
