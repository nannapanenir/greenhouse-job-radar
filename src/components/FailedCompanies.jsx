import { AlertTriangle, ChevronDown, ChevronRight } from 'lucide-react';
import { useState } from 'react';

export default function FailedCompanies({ failedCompanies }) {
  const [isOpen, setIsOpen] = useState(false);

  if (!failedCompanies || failedCompanies.length === 0) return null;

  return (
    <div className="bg-red-50 rounded-lg border border-red-200 overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-red-100 transition-colors"
      >
        <div className="flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-red-600" />
          <span className="text-sm font-medium text-red-700">
            Failed Companies ({failedCompanies.length})
          </span>
        </div>
        {isOpen ? (
          <ChevronDown className="w-4 h-4 text-red-400" />
        ) : (
          <ChevronRight className="w-4 h-4 text-red-400" />
        )}
      </button>

      {isOpen && (
        <div className="px-4 pb-4 border-t border-red-200">
          <div className="mt-3 space-y-2">
            {failedCompanies.map(company => (
              <div
                key={company.token}
                className="bg-white px-3 py-2 rounded-md text-sm"
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium text-slate-900">{company.name}</span>
                  <span className="text-xs text-slate-400">{company.token}</span>
                </div>
                <p className="text-xs text-red-600 mt-1">{company.error}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
