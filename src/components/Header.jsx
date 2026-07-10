import { Search } from 'lucide-react';

export default function Header() {
  return (
    <header className="bg-white border-b border-slate-200 sticky top-0 z-10">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
        <div className="flex items-center gap-3">
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
        </div>
        <p className="text-xs text-slate-400 mt-2">
          Track newly updated AI jobs and apply before opportunities become crowded.
        </p>
      </div>
    </header>
  );
}
