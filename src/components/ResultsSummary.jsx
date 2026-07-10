import { Building2, CheckCircle, XCircle, Clock, Briefcase, RefreshCw } from 'lucide-react';

export default function ResultsSummary({ summary }) {
  const {
    totalCompaniesSearched = 0,
    successfulCompanies = 0,
    failedCompanies = 0,
    totalJobs = 0,
    jobsLast3Hours = 0,
    jobsLast6Hours = 0,
    jobsLast24Hours = 0,
    lastFetched,
    isLoading
  } = summary || {};

  const formatTime = (date) => {
    if (!date) return 'Not fetched yet';
    return date.toLocaleTimeString('en-US', {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true
    });
  };

  return (
    <div className="bg-white rounded-lg border border-slate-200 p-4">
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-4 text-center">
        <div className="flex flex-col items-center">
          <Building2 className="w-5 h-5 text-slate-400 mb-1" />
          <span className="text-lg font-semibold text-slate-900">{totalCompaniesSearched}</span>
          <span className="text-xs text-slate-500">Companies Searched</span>
        </div>

        <div className="flex flex-col items-center">
          <CheckCircle className="w-5 h-5 text-emerald-500 mb-1" />
          <span className="text-lg font-semibold text-emerald-600">{successfulCompanies}</span>
          <span className="text-xs text-slate-500">Successful</span>
        </div>

        <div className="flex flex-col items-center">
          <XCircle className="w-5 h-5 text-red-400 mb-1" />
          <span className="text-lg font-semibold text-red-500">{failedCompanies}</span>
          <span className="text-xs text-slate-500">Failed</span>
        </div>

        <div className="flex flex-col items-center">
          <Briefcase className="w-5 h-5 text-amber-500 mb-1" />
          <span className="text-lg font-semibold text-slate-900">{totalJobs}</span>
          <span className="text-xs text-slate-500">Matching Jobs</span>
        </div>

        <div className="flex flex-col items-center">
          <Clock className="w-5 h-5 text-teal-500 mb-1" />
          <span className="text-lg font-semibold text-teal-600">{jobsLast3Hours}</span>
          <span className="text-xs text-slate-500">Last 3 Hours</span>
        </div>

        <div className="flex flex-col items-center">
          <Clock className="w-5 h-5 text-sky-500 mb-1" />
          <span className="text-lg font-semibold text-sky-600">{jobsLast6Hours}</span>
          <span className="text-xs text-slate-500">Last 6 Hours</span>
        </div>

        <div className="flex flex-col items-center">
          <Clock className="w-5 h-5 text-indigo-500 mb-1" />
          <span className="text-lg font-semibold text-indigo-600">{jobsLast24Hours}</span>
          <span className="text-xs text-slate-500">Last 24 Hours</span>
        </div>
      </div>

      <div className="flex items-center justify-center gap-2 mt-4 pt-3 border-t border-slate-100">
        <RefreshCw className={`w-4 h-4 text-slate-400 ${isLoading ? 'animate-spin' : ''}`} />
        <span className="text-sm text-slate-500">
          Last fetched: {formatTime(lastFetched)}
        </span>
      </div>
    </div>
  );
}
