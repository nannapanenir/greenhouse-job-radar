import { Clock } from 'lucide-react';

const QUICK_FILTERS = [
  { label: 'All Jobs', hours: Infinity },
  { label: 'Last 1 Hour', hours: 1 },
  { label: 'Last 3 Hours', hours: 3 },
  { label: 'Last 6 Hours', hours: 6 },
  { label: 'Last 12 Hours', hours: 12 },
  { label: 'Last 24 Hours', hours: 24 },
  { label: 'Last 2 Days', hours: 48 },
  { label: 'Last 3 Days', hours: 72 },
  { label: 'Last 7 Days', hours: 168 },
  { label: 'Last 14 Days', hours: 336 },
  { label: 'Last 30 Days', hours: 720 },
];

export default function TimeFilters({
  quickFilter,
  setQuickFilter,
  customHours,
  setCustomHours,
  customUnit,
  setCustomUnit,
  applyCustomFilter,
  clearCustomFilter
}) {
  return (
    <div className="bg-white rounded-lg border border-slate-200 p-4">
      <div className="flex items-center gap-2 mb-3">
        <Clock className="w-4 h-4 text-slate-500" />
        <span className="text-sm font-medium text-slate-700">Quick Time Filters</span>
      </div>

      <div className="flex flex-wrap gap-2">
        {QUICK_FILTERS.map(filter => (
          <button
            key={filter.label}
            onClick={() => {
              setQuickFilter(filter.hours);
              clearCustomFilter();
            }}
            className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
              quickFilter === filter.hours
                ? 'bg-amber-500 text-white'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            {filter.label}
          </button>
        ))}
      </div>

      <div className="mt-4 pt-4 border-t border-slate-100">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-sm text-slate-600">Updated Within</span>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <input
            type="number"
            min="1"
            value={customHours}
            onChange={(e) => setCustomHours(e.target.value)}
            placeholder="5"
            className="w-20 px-3 py-1.5 text-sm border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent"
          />
          <select
            value={customUnit}
            onChange={(e) => setCustomUnit(e.target.value)}
            className="px-3 py-1.5 text-sm border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent"
          >
            <option value="hours">Hours</option>
            <option value="days">Days</option>
          </select>
          <button
            onClick={applyCustomFilter}
            className="px-3 py-1.5 text-sm bg-slate-800 text-white rounded-md hover:bg-slate-700 transition-colors"
          >
            Apply Time Filter
          </button>
          <button
            onClick={clearCustomFilter}
            className="px-3 py-1.5 text-sm text-slate-600 hover:text-slate-800 transition-colors"
          >
            Clear
          </button>
        </div>
      </div>
    </div>
  );
}
