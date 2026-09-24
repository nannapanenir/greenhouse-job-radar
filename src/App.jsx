import { useState, useEffect, useCallback, useMemo } from 'react';
import { RefreshCw, Briefcase, AlertCircle } from 'lucide-react';
import Header from './components/Header';
import ResultsSummary from './components/ResultsSummary';
import TimeFilters from './components/TimeFilters';
import JobFilters from './components/JobFilters';
import JobCard from './components/JobCard';
import JobDetailsModal from './components/JobDetailsModal';
import CompanyPanel from './components/CompanyPanel';
import RoleProfilePanel from './components/RoleProfilePanel';
import FailedCompanies from './components/FailedCompanies';
import Footer from './components/Footer';
import { fetchAllJobs } from './services/greenhouseService';
import { getCompanies } from './services/companyConfigService';
import { isAgentDataEnabled, fetchAgentJobs } from './services/agentJobsService';
import {
  loadProfiles,
  saveProfiles,
  resetProfiles,
  resolveActiveProfileId,
  saveActiveProfileId,
  createProfileId
} from './services/roleProfileService';
import {
  applyRoleProfile,
  filterByTime,
  filterByStatus,
  searchJobs,
  filterByCompany,
  filterByMatchedKeyword,
  sortJobs,
  getUniqueCompanies,
  getUniqueMatchedKeywords
} from './utils/jobFilters';

const STATUS_STORAGE_KEY = 'aiJobRadar_jobStatuses';
const FILTER_STORAGE_KEY = 'aiJobRadar_filterSettings';

export default function App() {
  const [jobs, setJobs] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [lastFetched, setLastFetched] = useState(null);
  const [successfulCompanies, setSuccessfulCompanies] = useState([]);
  const [failedCompanies, setFailedCompanies] = useState([]);
  const [totalCompaniesSearched, setTotalCompaniesSearched] = useState(0);

  const [companies, setCompanies] = useState([]);
  const [companiesLoading, setCompaniesLoading] = useState(true);
  const [companiesError, setCompaniesError] = useState(null);

  // Opt-in (?data=agent): load the Python agent's combined jobs.json instead of
  // fetching Greenhouse live. The live flow stays the default until verified.
  const [useAgentData] = useState(isAgentDataEnabled);
  const [fetchError, setFetchError] = useState(null);

  const [selectedJob, setSelectedJob] = useState(null);

  const [quickFilter, setQuickFilter] = useState(24);
  const [customHours, setCustomHours] = useState('');
  const [customUnit, setCustomUnit] = useState('hours');
  const [isCustomFilterActive, setIsCustomFilterActive] = useState(false);
  const [maxAgeHours, setMaxAgeHours] = useState(24);

  const [searchTerm, setSearchTerm] = useState('');
  const [companyFilter, setCompanyFilter] = useState('');
  const [keywordFilter, setKeywordFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [sortBy, setSortBy] = useState('newest');

  const [profiles, setProfiles] = useState(loadProfiles);
  const [activeProfileId, setActiveProfileId] = useState(() => resolveActiveProfileId(profiles));

  const activeProfile = profiles.find(p => p.id === activeProfileId) ?? profiles[0] ?? null;

  useEffect(() => {
    if (activeProfile) saveActiveProfileId(activeProfile.id);
  }, [activeProfile]);

  const [jobStatuses, setJobStatuses] = useState(() => {
    const stored = localStorage.getItem(STATUS_STORAGE_KEY);
    return stored ? JSON.parse(stored) : {};
  });

  useEffect(() => {
    localStorage.setItem(STATUS_STORAGE_KEY, JSON.stringify(jobStatuses));
  }, [jobStatuses]);

  useEffect(() => {
    const stored = localStorage.getItem(FILTER_STORAGE_KEY);
    if (stored) {
      const settings = JSON.parse(stored);
      setQuickFilter(settings.quickFilter ?? 24);
      setMaxAgeHours(settings.maxAgeHours ?? 24);
    }
  }, []);

  useEffect(() => {
    localStorage.setItem(FILTER_STORAGE_KEY, JSON.stringify({
      quickFilter,
      maxAgeHours
    }));
  }, [quickFilter, maxAgeHours]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const loaded = await getCompanies();
        if (!cancelled) {
          setCompanies(loaded);
          setCompaniesLoading(false);
        }
      } catch (error) {
        if (!cancelled) {
          setCompaniesError(error.message);
          setCompaniesLoading(false);
        }
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const handleFetchJobs = async () => {
    if (!useAgentData && (companiesError || companies.length === 0)) return;
    setIsLoading(true);
    setFetchError(null);
    try {
      const result = useAgentData ? await fetchAgentJobs() : await fetchAllJobs(companies);
      setJobs(result.jobs);
      setSuccessfulCompanies(result.successfulCompanies);
      setFailedCompanies(result.failedCompanies);
      setTotalCompaniesSearched(result.totalCompaniesSearched);
      setLastFetched(result.generatedAt ?? new Date());
    } catch (error) {
      console.error('Failed to fetch jobs:', error);
      if (useAgentData) setFetchError(error.message);
    } finally {
      setIsLoading(false);
    }
  };

  const applyCustomFilter = () => {
    const hours = parseInt(customHours, 10);
    if (hours > 0) {
      const convertedHours = customUnit === 'days' ? hours * 24 : hours;
      setMaxAgeHours(convertedHours);
      setQuickFilter(null);
      setIsCustomFilterActive(true);
    }
  };

  const clearCustomFilter = () => {
    setCustomHours('');
    setIsCustomFilterActive(false);
  };

  const handleQuickFilter = (hours) => {
    setQuickFilter(hours);
    setMaxAgeHours(hours);
    setIsCustomFilterActive(false);
  };

  const handleStatusChange = useCallback((jobUrl, status) => {
    setJobStatuses(prev => ({
      ...prev,
      [jobUrl]: status
    }));
  }, []);

  const handleSelectProfile = (id) => {
    setActiveProfileId(id);
    setKeywordFilter('');
  };

  const handleSaveProfile = (profile) => {
    const id = profile.id ?? createProfileId(profile.name, profiles);
    const saved = { ...profile, id };
    const next = profile.id
      ? profiles.map(p => (p.id === id ? saved : p))
      : [...profiles, saved];
    setProfiles(next);
    saveProfiles(next);
    handleSelectProfile(id);
  };

  const handleDeleteProfile = (id) => {
    const next = profiles.filter(p => p.id !== id);
    if (next.length === 0) return;
    setProfiles(next);
    saveProfiles(next);
    if (id === activeProfile?.id) {
      handleSelectProfile(next[0].id);
    }
  };

  const handleResetProfiles = () => {
    const defaults = resetProfiles();
    setProfiles(defaults);
    handleSelectProfile(resolveActiveProfileId(defaults));
  };

  const roleJobs = useMemo(() => applyRoleProfile(jobs, activeProfile), [jobs, activeProfile]);

  let filteredJobs = roleJobs;

  if (maxAgeHours !== Infinity) {
    filteredJobs = filterByTime(filteredJobs, maxAgeHours);
  }

  filteredJobs = searchJobs(filteredJobs, searchTerm);
  filteredJobs = filterByCompany(filteredJobs, companyFilter);
  filteredJobs = filterByMatchedKeyword(filteredJobs, keywordFilter);
  filteredJobs = filterByStatus(filteredJobs, statusFilter ? [statusFilter] : [], jobStatuses);
  filteredJobs = sortJobs(filteredJobs, sortBy);

  const filterCompanies = getUniqueCompanies(roleJobs);
  const keywords = getUniqueMatchedKeywords(roleJobs);

  const jobsLast3Hours = roleJobs.filter(j => j.jobAgeHours <= 3).length;
  const jobsLast6Hours = roleJobs.filter(j => j.jobAgeHours <= 6).length;
  const jobsLast24Hours = roleJobs.filter(j => j.jobAgeHours <= 24).length;

  return (
    <div className="min-h-screen bg-slate-50">
      <Header />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-4">
        <div className="flex justify-center">
          <button
            onClick={handleFetchJobs}
            disabled={isLoading || (!useAgentData && (companiesLoading || !!companiesError))}
            className={`flex items-center gap-2 px-6 py-3 text-lg font-medium rounded-lg transition-all ${
              isLoading
                ? 'bg-slate-300 text-slate-500 cursor-not-allowed'
                : 'bg-amber-500 text-white hover:bg-amber-600 shadow-md hover:shadow-lg'
            }`}
          >
            <RefreshCw className={`w-5 h-5 ${isLoading ? 'animate-spin' : ''}`} />
            {isLoading ? 'Fetching Latest Jobs...' : !useAgentData && companiesLoading ? 'Loading Companies...' : 'Fetch Latest Jobs'}
          </button>
        </div>

        {companiesError && !useAgentData && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-2">
            <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
            <span className="text-sm text-red-700">Unable to load company configuration.</span>
          </div>
        )}

        {fetchError && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-2">
            <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
            <span className="text-sm text-red-700">{fetchError}</span>
          </div>
        )}

        <ResultsSummary
          summary={{
            totalCompaniesSearched,
            successfulCompanies: successfulCompanies.length,
            failedCompanies: failedCompanies.length,
            totalJobs: roleJobs.length,
            jobsLast3Hours,
            jobsLast6Hours,
            jobsLast24Hours,
            lastFetched,
            isLoading
          }}
        />

        <FailedCompanies failedCompanies={failedCompanies} />

        <TimeFilters
          quickFilter={quickFilter}
          setQuickFilter={handleQuickFilter}
          customHours={customHours}
          setCustomHours={setCustomHours}
          customUnit={customUnit}
          setCustomUnit={setCustomUnit}
          applyCustomFilter={applyCustomFilter}
          clearCustomFilter={clearCustomFilter}
        />

        <JobFilters
          searchTerm={searchTerm}
          setSearchTerm={setSearchTerm}
          companyFilter={companyFilter}
          setCompanyFilter={setCompanyFilter}
          keywordFilter={keywordFilter}
          setKeywordFilter={setKeywordFilter}
          statusFilter={statusFilter}
          setStatusFilter={setStatusFilter}
          sortBy={sortBy}
          setSortBy={setSortBy}
          companies={filterCompanies}
          keywords={keywords}
          jobStatuses={jobStatuses}
        />

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2">
            <div className="mb-3 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Briefcase className="w-4 h-4 text-slate-500" />
                <span className="text-sm font-medium text-slate-700">
                  {filteredJobs.length} Matching Jobs
                </span>
              </div>
            </div>

            {filteredJobs.length === 0 ? (
              <div className="bg-white rounded-lg border border-slate-200 p-8 text-center">
                <p className="text-slate-500">
                  {jobs.length === 0
                    ? 'No jobs fetched yet. Click "Fetch Latest Jobs" to get started.'
                    : `No matching jobs found for ${activeProfile?.name ?? 'this role'}. Try changing the time filter, switching roles, or editing the role's keywords.`}
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {filteredJobs.map(job => (
                  <JobCard
                    key={job.absoluteUrl || `${job.companyToken}-${job.id}`}
                    job={job}
                    onViewDetails={setSelectedJob}
                    jobStatus={jobStatuses[job.absoluteUrl] || 'New'}
                    onStatusChange={handleStatusChange}
                  />
                ))}
              </div>
            )}
          </div>

          <div className="space-y-4">
            <CompanyPanel companies={companies} />
            <RoleProfilePanel
              profiles={profiles}
              activeProfile={activeProfile}
              onSelectProfile={handleSelectProfile}
              onSaveProfile={handleSaveProfile}
              onDeleteProfile={handleDeleteProfile}
              onResetProfiles={handleResetProfiles}
            />
          </div>
        </div>
      </main>

      {selectedJob && (
        <JobDetailsModal
          job={selectedJob}
          onClose={() => setSelectedJob(null)}
          jobStatus={jobStatuses[selectedJob.absoluteUrl] || 'New'}
          onStatusChange={handleStatusChange}
        />
      )}

      <Footer />
    </div>
  );
}
