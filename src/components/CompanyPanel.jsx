import { Building2, ChevronDown, ChevronRight } from 'lucide-react';
import { useState } from 'react';
import { getCompaniesConfig } from '../services/greenhouseService';

export default function CompanyPanel() {
  const [isOpen, setIsOpen] = useState(false);
  const companies = getCompaniesConfig();

  const enabledCompanies = companies.filter(c => c.enabled);
  const disabledCompanies = companies.filter(c => !c.enabled);

  return (
    <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-4 py-3 flex items-center justify-between hover:bg-slate-50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Building2 className="w-4 h-4 text-slate-500" />
          <span className="text-sm font-medium text-slate-700">Companies</span>
          <div className="flex gap-2 text-xs text-slate-500">
            <span>{companies.length} total</span>
            <span className="text-emerald-600">{enabledCompanies.length} enabled</span>
            {disabledCompanies.length > 0 && (
              <span className="text-slate-400">{disabledCompanies.length} disabled</span>
            )}
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
            <span className="text-xs font-medium text-slate-500">Enabled Companies</span>
            <div className="flex flex-wrap gap-2 mt-2">
              {enabledCompanies.map(company => (
                <span
                  key={company.token}
                  className="px-2 py-1 text-xs bg-emerald-50 text-emerald-700 rounded-md border border-emerald-200"
                >
                  {company.name}
                </span>
              ))}
            </div>
          </div>

          {disabledCompanies.length > 0 && (
            <div className="mt-3">
              <span className="text-xs font-medium text-slate-400">Disabled Companies</span>
              <div className="flex flex-wrap gap-2 mt-2">
                {disabledCompanies.map(company => (
                  <span
                    key={company.token}
                    className="px-2 py-1 text-xs bg-slate-100 text-slate-500 rounded-md"
                  >
                    {company.name}
                  </span>
                ))}
              </div>
            </div>
          )}

          <p className="text-xs text-slate-400 mt-3">
            Edit <code className="bg-slate-100 px-1 rounded">src/config/greenhouse-companies.json</code> to modify companies.
          </p>
        </div>
      )}
    </div>
  );
}
