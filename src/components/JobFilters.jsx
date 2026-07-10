import { Search, Filter, X } from 'lucide-react';

export default function JobFilters({
  searchTerm,
  setSearchTerm,
  companyFilter,
  setCompanyFilter,
  keywordFilter,
  setKeywordFilter,
  statusFilter,
  setStatusFilter,
  sortBy,
  setSortBy,
  companies,
  keywords,
  jobStatuses
}) {
  const statusOptions = ['New', 'Saved', 'Applied', 'Not Interested'];

  const clearAllFilters = () => {
    setSearchTerm('');
    setCompanyFilter('');
    setKeywordFilter('');
    setStatusFilter('');
    setSortBy('newest');
  };

  const hasActiveFilters = searchTerm || companyFilter || keywordFilter || statusFilter;

  return (
    <div className="bg-white rounded-lg border border-slate-200 p-4">
      <div className="flex items-center gap-2 mb-3">
        <Filter className="w-4 h-4 text-slate-500" />
        <span className="text-sm font-medium text-slate-700">Search & Filters</span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-3">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search jobs or companies"
            className="w-full pl-9 pr-3 py-2 text-sm border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent"
          />
        </div>

        <select
          value={companyFilter}
          onChange={(e) => setCompanyFilter(e.target.value)}
          className="px-3 py-2 text-sm border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent"
        >
          <option value="">All Companies</option>
          {companies.map(company => (
            <option key={company} value={company}>{company}</option>
          ))}
        </select>

        <select
          value={keywordFilter}
          onChange={(e) => setKeywordFilter(e.target.value)}
          className="px-3 py-2 text-sm border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent"
        >
          <option value="">All Keywords</option>
          {keywords.map(keyword => (
            <option key={keyword} value={keyword}>{keyword}</option>
          ))}
        </select>

        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-3 py-2 text-sm border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent"
        >
          <option value="">All Statuses</option>
          {statusOptions.map(status => (
            <option key={status} value={status}>{status}</option>
          ))}
        </select>

        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value)}
          className="px-3 py-2 text-sm border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent"
        >
          <option value="newest">Newest Updated</option>
          <option value="oldest">Oldest Updated</option>
          <option value="company">Company A-Z</option>
          <option value="title">Job Title A-Z</option>
        </select>
      </div>

      {hasActiveFilters && (
        <div className="mt-3 pt-3 border-t border-slate-100">
          <button
            onClick={clearAllFilters}
            className="flex items-center gap-1 px-3 py-1.5 text-sm text-slate-600 hover:text-slate-800 transition-colors"
          >
            <X className="w-4 h-4" />
            Clear Filters
          </button>
        </div>
      )}
    </div>
  );
}
