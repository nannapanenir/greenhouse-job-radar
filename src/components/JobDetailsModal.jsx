import { X, ExternalLink, MapPin, Clock, Building2, Calendar } from 'lucide-react';
import { SOURCE_LABELS } from '../services/agentJobsService';

const FRESHNESS_BADGES = {
  VERY_FRESH: { label: 'Very Fresh', color: 'bg-emerald-100 text-emerald-700 border-emerald-200' },
  FRESH: { label: 'Fresh', color: 'bg-teal-100 text-teal-700 border-teal-200' },
  TODAY: { label: 'Today', color: 'bg-sky-100 text-sky-700 border-sky-200' },
  RECENT: { label: 'Recent', color: 'bg-amber-100 text-amber-700 border-amber-200' },
  OLDER: { label: null, color: '' }
};

export default function JobDetailsModal({ job, onClose, jobStatus, onStatusChange }) {
  if (!job) return null;

  const badge = FRESHNESS_BADGES[job.freshnessLevel] || FRESHNESS_BADGES.OLDER;

  const formatTimestamp = (timestamp) => {
    if (!timestamp) return 'Unknown';
    const date = new Date(timestamp);
    return date.toLocaleString('en-US', {
      weekday: 'long',
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true
    });
  };

  const statusColors = {
    'New': 'bg-slate-100 text-slate-600',
    'Saved': 'bg-blue-100 text-blue-600',
    'Applied': 'bg-green-100 text-green-600',
    'Not Interested': 'bg-red-100 text-red-600'
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex min-h-full items-center justify-center p-4">
        <div
          className="fixed inset-0 bg-black/50 transition-opacity"
          onClick={onClose}
        />

        <div className="relative bg-white rounded-xl shadow-xl max-w-3xl w-full max-h-[90vh] overflow-y-auto">
          <div className="sticky top-0 bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between">
            <h2 className="text-xl font-semibold text-slate-900 truncate pr-8">
              {job.title}
            </h2>
            <button
              onClick={onClose}
              className="p-2 text-slate-400 hover:text-slate-600 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          <div className="p-6">
            <div className="flex flex-wrap items-center gap-3 mb-4">
              <div className="flex items-center gap-1 text-slate-600">
                <Building2 className="w-4 h-4" />
                <span className="font-medium">{job.companyName}</span>
              </div>
              <div className="flex items-center gap-1 text-slate-600">
                <MapPin className="w-4 h-4" />
                <span>{job.location}</span>
              </div>
              {badge.label && (
                <span className={`px-2 py-0.5 text-xs font-medium rounded-full border ${badge.color}`}>
                  {badge.label}
                </span>
              )}
            </div>

            <div className="flex items-center gap-2 text-sm text-slate-500 mb-4">
              <Clock className="w-4 h-4" />
              <span className="font-medium">{job.jobAgeText}</span>
            </div>

            <div className="flex items-center gap-2 text-sm text-slate-500 mb-4">
              <Calendar className="w-4 h-4" />
              <span>Last updated: {formatTimestamp(job.updatedAt)}</span>
            </div>

            {job.matchedKeywords && job.matchedKeywords.length > 0 && (
              <div className="mb-4">
                <span className="text-sm font-medium text-slate-700">Matched AI Keywords:</span>
                <div className="flex flex-wrap gap-1 mt-2">
                  {job.matchedKeywords.map(keyword => (
                    <span
                      key={keyword}
                      className="px-2 py-1 text-sm bg-amber-50 text-amber-700 rounded-full border border-amber-200"
                    >
                      {keyword}
                    </span>
                  ))}
                </div>
              </div>
            )}

            <div className="mb-4">
              <span className="text-sm font-medium text-slate-700">Status:</span>
              <div className="flex gap-2 mt-2">
                {['New', 'Saved', 'Applied', 'Not Interested'].map(status => (
                  <button
                    key={status}
                    onClick={() => onStatusChange(job.absoluteUrl, status)}
                    className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
                      jobStatus === status
                        ? statusColors[status]
                        : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                    }`}
                  >
                    {status}
                  </button>
                ))}
              </div>
            </div>

            <a
              href={job.absoluteUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-4 py-2 bg-amber-500 text-white font-medium rounded-md hover:bg-amber-600 transition-colors mb-6"
            >
              Apply on {SOURCE_LABELS[job.source] || 'Greenhouse'}
              <ExternalLink className="w-4 h-4" />
            </a>

            <div className="border-t border-slate-200 pt-6">
              <h3 className="text-lg font-semibold text-slate-900 mb-4">Job Description</h3>
              <div className="prose prose-slate max-w-none text-sm text-slate-600 whitespace-pre-wrap">
                {job.cleanContent || 'No description available.'}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
