import { useEffect, useState } from 'react';
import App from './App';
import Header from './components/Header';
import Footer from './components/Footer';
import ResumeAIPage from './features/resume-ai/ResumeAIPage';
import ApplicationsPage from './features/applications/ApplicationsPage';
import { setPendingJob } from './features/resume-ai/services/resumeStore';
import { toCommonJob } from './shared/models/commonJob';
import { ROUTES, navigate, useRoute } from './shared/services/router';

/**
 * App shell: Jobs | Resume AI | Applications. Pages stay mounted once
 * visited (hidden, not unmounted) so fetched jobs and filters survive
 * navigation.
 */
export default function Root() {
  const route = useRoute();
  const [visited, setVisited] = useState(() => ({ [route]: true }));
  const [incoming, setIncoming] = useState(null);

  useEffect(() => {
    setVisited(v => (v[route] ? v : { ...v, [route]: true }));
  }, [route]);

  // Job card / details "Tailor Resume": hand the Common Job to Resume AI.
  const handleTailorResume = uiJob => {
    const job = toCommonJob(uiJob);
    setPendingJob(job);
    setIncoming({ job, at: Date.now() });
    navigate(ROUTES.resumeAI);
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <Header route={route} onNavigate={navigate} />
      <div className="flex-1">
        <div hidden={route !== ROUTES.jobs}>
          <App onTailorResume={handleTailorResume} />
        </div>
        {visited[ROUTES.resumeAI] && (
          <div hidden={route !== ROUTES.resumeAI}>
            <ResumeAIPage incoming={incoming} onGoToJobs={() => navigate(ROUTES.jobs)} />
          </div>
        )}
        {visited[ROUTES.applications] && (
          <div hidden={route !== ROUTES.applications}>
            <ApplicationsPage active={route === ROUTES.applications} />
          </div>
        )}
      </div>
      <Footer />
    </div>
  );
}
