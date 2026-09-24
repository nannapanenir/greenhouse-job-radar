import { useState } from 'react';
import { AlertCircle, FileSearch, Loader2, RefreshCw, Sparkles } from 'lucide-react';
import { useResumeAI } from './useResumeAI';
import ChangeReview from './components/ChangeReview';
import CareerProfile from './components/CareerProfile';
import JobMatchPanel from './components/JobMatchPanel';
import KeywordsTab from './components/KeywordsTab';
import MatchAnalysis from './components/MatchAnalysis';
import ResumeChat from './components/ResumeChat';
import ResumePreview from './components/ResumePreview';
import ResumeSettings from './components/ResumeSettings';
import ResumeUpload from './components/ResumeUpload';
import { Card } from './components/ui';

const VIEWS = [['workspace', 'Workspace'], ['profile', 'Career Profile'], ['settings', 'Settings']];
const TABS = [['changes', 'Changes'], ['keywords', 'Keywords'], ['match', 'Match Analysis'], ['original', 'Original']];

/** Resume AI: Master Resume -> Candidate Profile + Job -> reviewed, validated tailoring -> DOCX/PDF. */
export default function ResumeAIPage({ incoming, onGoToJobs }) {
  const { state, actions } = useResumeAI({ incoming });
  const [view, setView] = useState('workspace');
  const [tab, setTab] = useState('changes');
  const { apiStatus, aiStatus, profile, masterResume, session, busy, error } = state;
  const aiConfigured = Boolean(aiStatus?.configured);

  const upload = compact => (
    <ResumeUpload compact={compact} masterResume={masterResume} onUpload={actions.uploadResume}
      aiConfigured={aiConfigured} busy={busy} onOpenSettings={() => setView('settings')} />
  );

  return (
    <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-4" data-testid="resume-ai-page">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-amber-500" />
          <h1 className="text-lg font-semibold text-slate-900">Resume AI</h1>
          <span className={`px-2 py-0.5 text-xs rounded-full ${apiStatus === 'online' ? 'bg-emerald-50 text-emerald-700' : apiStatus === 'offline' ? 'bg-red-50 text-red-700' : 'bg-slate-100 text-slate-500'}`} data-testid="api-status">
            API {apiStatus}{apiStatus === 'online' ? ` • AI ${aiConfigured ? `${aiStatus.provider} / ${aiStatus.model}` : 'not configured (local engine)'}` : ''}
          </span>
        </div>
        <div className="flex gap-1 bg-slate-100 p-1 rounded-lg" role="tablist" aria-label="Resume AI views">
          {VIEWS.map(([key, label]) => (
            <button key={key} type="button" role="tab" aria-selected={view === key} onClick={() => setView(key)}
              className={`px-3 py-1.5 text-sm rounded-md ${view === key ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600 hover:text-slate-800'}`}>{label}</button>
          ))}
        </div>
      </div>

      {apiStatus === 'offline' && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex flex-wrap items-center gap-2 text-sm text-red-700">
          <AlertCircle className="w-5 h-5" />
          The Job Radar Python API isn't reachable. Start it with <code className="bg-white px-1 rounded">uvicorn backend.main:app --port 8000</code>.
          <button type="button" onClick={actions.refreshStatus} className="inline-flex items-center gap-1 text-red-800 hover:underline"><RefreshCw className="w-4 h-4" />Retry</button>
        </div>
      )}
      {busy && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 flex items-center gap-2 text-sm text-amber-800" data-testid="busy">
          <Loader2 className="w-4 h-4 animate-spin" />{busy}
        </div>
      )}
      {error && !busy && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 flex items-center justify-between gap-2 text-sm text-red-700" data-testid="error">
          <span>{error}</span><button type="button" onClick={actions.dismissError} className="text-xs hover:underline">Dismiss</button>
        </div>
      )}

      {view === 'profile' && <CareerProfile profile={profile} masterResume={masterResume} onUpdate={actions.updateProfile} uploadControl={upload(true)} />}
      {view === 'settings' && <ResumeSettings aiStatus={aiStatus} apiStatus={apiStatus} mode={state.mode} actions={actions} />}

      {view === 'workspace' && (
        <>
          {!profile && upload(false)}
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
            <div className="lg:col-span-3">
              <Card title={session ? `Resume Preview — ${session.jobTitle}` : 'Resume Preview'} icon={FileSearch}
                actions={profile ? upload(true) : null}>
                {profile ? <ResumePreview profile={profile} session={session} />
                  : <p className="text-sm text-slate-500">Your resume appears here once your Master Resume is uploaded.</p>}
              </Card>
            </div>
            <div className="lg:col-span-2 space-y-4">
              <JobMatchPanel state={state} actions={actions} onGoToJobs={onGoToJobs} />
              <ResumeChat chatLog={state.chatLog} busy={busy} onSend={actions.sendChat} />
            </div>
          </div>

          {session && (
            <section className="bg-white rounded-lg border border-slate-200" data-testid="workflow-tabs">
              <div className="flex gap-1 border-b border-slate-100 px-2" role="tablist">
                {TABS.map(([key, label]) => (
                  <button key={key} type="button" role="tab" aria-selected={tab === key} onClick={() => setTab(key)}
                    className={`px-3 py-2 text-sm border-b-2 -mb-px ${tab === key ? 'border-amber-500 text-slate-900' : 'border-transparent text-slate-500 hover:text-slate-700'}`}>
                    {label}{key === 'changes' ? ` (${session.changes.length})` : ''}
                  </button>
                ))}
              </div>
              <div className="p-4">
                {tab === 'changes' && <ChangeReview session={session} activeIndex={state.activeChangeIndex} actions={actions} />}
                {tab === 'keywords' && <KeywordsTab session={session} />}
                {tab === 'match' && <MatchAnalysis session={session} profile={profile} />}
                {tab === 'original' && <ResumePreview profile={profile} session={session} original />}
              </div>
            </section>
          )}
        </>
      )}
    </main>
  );
}
