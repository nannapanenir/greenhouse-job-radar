import { Search } from 'lucide-react';

const NAV = [
  ['/', 'Jobs'],
  ['/resume-ai', 'Resume AI'],
  ['/applications', 'Applications']
];

export default function Header({ route = '/', onNavigate }) {
  return (
    <header className="bg-white border-b border-slate-200 sticky top-0 z-10">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center justify-center w-10 h-10 rounded-lg bg-amber-500">
            <Search className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-semibold text-slate-900">
              AI Job Radar
            </h1>
            <p className="text-sm text-slate-500">
              Find fresh Applied AI, LLM, RAG, Machine Learning, and Generative AI opportunities
            </p>
          </div>
          {onNavigate && (
            <nav className="flex gap-1 sm:ml-auto" aria-label="Main">
              {NAV.map(([path, label]) => (
                <a
                  key={path}
                  href={path}
                  onClick={event => { event.preventDefault(); onNavigate(path); }}
                  aria-current={route === path ? 'page' : undefined}
                  className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
                    route === path ? 'bg-amber-500 text-white' : 'text-slate-600 hover:bg-slate-100'
                  }`}
                >
                  {label}
                </a>
              ))}
            </nav>
          )}
        </div>
        <p className="text-xs text-slate-400 mt-2">
          Track newly updated AI jobs and apply before opportunities become crowded.
        </p>
      </div>
    </header>
  );
}
