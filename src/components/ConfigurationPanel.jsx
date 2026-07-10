import { Settings, ChevronDown, ChevronRight } from 'lucide-react';
import { useState } from 'react';
import { getJobFiltersConfig } from '../services/greenhouseService';

export default function ConfigurationPanel() {
  const [isOpen, setIsOpen] = useState(false);
  const filters = getJobFiltersConfig();

  return (
    <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-slate-50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Settings className="w-4 h-4 text-slate-500" />
          <span className="text-sm font-medium text-slate-700">Job Configuration</span>
          <div className="flex gap-2 text-xs text-slate-500">
            <span>{filters.includeKeywords.length} keywords</span>
            <span>{filters.excludeTitleKeywords.length} exclusions</span>
            <span>{filters.locationKeywords.length} locations</span>
          </div>
        </div>
        {isOpen ? (
          <ChevronDown className="w-4 h-4 text-slate-400" />
        ) : (
          <ChevronRight className="w-4 h-4 text-slate-400" />
        )}
      </button>

      {isOpen && (
        <div className="px-4 pb-4 border-t border-slate-100">
          <div className="mt-3">
            <span className="text-xs font-medium text-slate-500">Include Keywords</span>
            <div className="flex flex-wrap gap-1 mt-2">
              {filters.includeKeywords.map(keyword => (
                <span
                  key={keyword}
                  className="px-2 py-0.5 text-xs bg-emerald-50 text-emerald-700 rounded-full"
                >
                  {keyword}
                </span>
              ))}
            </div>
          </div>

          <div className="mt-3">
            <span className="text-xs font-medium text-slate-500">Exclude Title Keywords</span>
            <div className="flex flex-wrap gap-1 mt-2">
              {filters.excludeTitleKeywords.map(keyword => (
                <span
                  key={keyword}
                  className="px-2 py-0.5 text-xs bg-red-50 text-red-700 rounded-full"
                >
                  {keyword}
                </span>
              ))}
            </div>
          </div>

          <div className="mt-3">
            <span className="text-xs font-medium text-slate-500">Location Keywords</span>
            <div className="flex flex-wrap gap-1 mt-2">
              {filters.locationKeywords.map(keyword => (
                <span
                  key={keyword}
                  className="px-2 py-0.5 text-xs bg-sky-50 text-sky-700 rounded-full"
                >
                  {keyword}
                </span>
              ))}
            </div>
          </div>

          <p className="text-xs text-slate-400 mt-3">
            Edit <code className="bg-slate-100 px-1 rounded">src/config/job-filters.json</code> to modify filters.
          </p>
        </div>
      )}
    </div>
  );
}
