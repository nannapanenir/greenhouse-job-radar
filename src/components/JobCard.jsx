import { ExternalLink, MapPin, Clock, Building2 } from 'lucide-react';
import { getPreviewText } from '../utils/htmlCleaner';

const FRESHNESS_BADGES = {
  VERY_FRESH: { label: 'Very Fresh', color: 'bg-emerald-100 text-emerald-700 border-emerald-200' },
  FRESH: { label: 'Fresh', color: 'bg-teal-100 text-teal-700 border-teal-200' },
  TODAY: { label: 'Today', color: 'bg-sky-100 text-sky-700 border-sky-200' },
  RECENT: { label: 'Recent', color: 'bg-amber-100 text-amber-700 border-amber-200' },
  OLDER: { label: null, color: '' }
};

export default function JobCard({ job, onViewDetails, jobStatus, onStatusChange }) {
  const badge = FRESHNESS_BADGES[job.freshnessLevel] || FRESHNESS_BADGES.OLDER;
  const preview = getPreviewText(job.cleanContent, 150);

  const statusColors = {
    'New': 'bg-slate-100 text-slate-600',
    'Saved': 'bg-blue-100 text-blue-600',
    'Applied': 'bg-green-100 text-green-600',
    'Not Interested': 'bg-red-100 text-red-600'
  };

  return (
    <div className="bg-white rounded-lg border border-slate-200 p-4 hover:shadow-md transition-shadow">
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-start gap-2 flex-wrap">
            <h3 className="text-lg font-semibold text-slate-900 truncate">
              {job.title}
            </h3>
            {badge.label && (
              <span className={`px-2 py-0.5 text-xs font-medium rounded-full border ${badge.color}`}>
                {badge.label}
              </span>
            )}
          </div>

          <div className="flex items-center gap-4 mt-2 text-sm text-slate-600">
            <div className="flex items-center gap-1">
              <Building2 className="w-4 h-4" />
              <span className="font-medium">{job.companyName}</span>
            </div>
            <div className="flex items-center gap-1">
              <MapPin className="w-4 h-4" />
              <span>{job.location}</span>
            </div>
          </div>

          <div className="flex items-center gap-1 mt-2 text-sm text-slate-500">
            <Clock className="w-4 h-4" />
            <span>{job.jobAgeText}</span>
          </div>

          {job.matchedKeywords && job.matchedKeywords.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-3">
              <span className="text-xs text-slate-500">Matched:</span>
              {job.matchedKeywords.slice(0, 5).map(keyword => (
                <span
                  key={keyword}
                  className="px-2 py-0.5 text-xs bg-amber-50 text-amber-700 rounded-full"
                >
                  {keyword}
                </span>
              ))}
              {job.matchedKeywords.length > 5 && (
                <span className="text-xs text-slate-500">+{job.matchedKeywords.length - 5} more</span>
              )}
            </div>
          )}

          {preview && (
            <p className="mt-3 text-sm text-slate-600 line-clamp-2">
              {preview}
            </p>
          )}
        </div>

        <div className="flex flex-col gap-2 sm:items-end">
          <div className="flex gap-2">
            <button
              onClick={() => onViewDetails(job)}
              className="px-3 py-1.5 text-sm font-medium text-slate-700 bg-slate-100 rounded-md hover:bg-slate-200 transition-colors"
            >
              View Details
            </button>
            <a
              href={job.absoluteUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium text-white bg-amber-500 rounded-md hover:bg-amber-600 transition-colors"
            >
              Apply
              <ExternalLink className="w-4 h-4" />
            </a>
          </div>

          <div className="flex gap-1">
            {['New', 'Saved', 'Applied', 'Not Interested'].map(status => (
              <button
                key={status}
                onClick={() => onStatusChange(job.absoluteUrl, status)}
                className={`px-2 py-1 text-xs rounded transition-colors ${
                  jobStatus === status
                    ? statusColors[status]
                    : 'bg-slate-50 text-slate-500 hover:bg-slate-100'
                }`}
              >
                {status}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
