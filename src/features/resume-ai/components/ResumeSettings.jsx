import { useEffect, useState } from 'react';
import { KeyRound, Settings } from 'lucide-react';
import { Button, Card, inputClass } from './ui';

const LABELS = { openrouter: 'OpenRouter (cloud)', gemini: 'Google Gemini (cloud)', local: 'Local server (Ollama, LM Studio, llama.cpp, vLLM…)' };
const MODEL_HINTS = { openrouter: 'e.g. openai/gpt-4o-mini', gemini: 'e.g. gemini-2.0-flash', local: 'e.g. llama3.2:3b' };

/** AI provider settings. The key is sent once to the Python server and never stored in the browser. */
export default function ResumeSettings({ aiStatus, apiStatus, mode, actions }) {
  const [provider, setProvider] = useState(aiStatus?.provider || 'openrouter');
  const [model, setModel] = useState(aiStatus?.model || '');
  const [baseUrl, setBaseUrl] = useState(aiStatus?.baseUrl || '');
  const [apiKey, setApiKey] = useState('');
  const [saved, setSaved] = useState(null);

  useEffect(() => {
    if (aiStatus) {
      setProvider(aiStatus.provider);
      setModel(aiStatus.model || '');
      setBaseUrl(aiStatus.baseUrl || '');
    }
  }, [aiStatus]);

  const editable = aiStatus?.editable !== false;
  const save = async () => {
    const result = await actions.saveAISettings({ provider, model, apiKey, baseUrl: provider === 'local' ? baseUrl : '' });
    setApiKey(''); // never keep the key in browser state
    if (result) setSaved('Saved on the server.');
  };

  return (
    <div className="space-y-4" data-testid="resume-settings">
      <Card title="Tailoring mode" icon={Settings}>
        <p className="text-xs text-slate-500 mb-2">All modes stay truthful — only verified facts are used.</p>
        {[['conservative', 'Conservative — minimal rewording, required skills only'], ['balanced', 'Balanced (default) — required + preferred skills'], ['strong', 'Strong Targeting — also strengthens the summary']].map(([value, label]) => (
          <label key={value} className="flex items-center gap-2 text-sm text-slate-700">
            <input type="radio" name="mode" checked={mode === value} onChange={() => actions.setMode(value)} />{label}
          </label>
        ))}
      </Card>

      <Card title="AI provider" icon={KeyRound}>
        {apiStatus !== 'online' ? (
          <p className="text-sm text-red-700">The Python API is not reachable, so AI settings can't be loaded.</p>
        ) : (
          <>
            <p className={`text-sm ${aiStatus?.configured ? 'text-emerald-700' : 'text-slate-600'}`} data-testid="ai-status">
              {aiStatus?.configured
                ? `✅ Connected: ${LABELS[aiStatus.provider]} — ${aiStatus.model}${aiStatus.baseUrl ? ` at ${aiStatus.baseUrl}` : ''} (configured via ${aiStatus.source === 'env' ? 'server environment' : 'server settings file'}).`
                : 'Not connected — tailoring uses the built-in local matching engine; resume extraction needs a provider.'}
            </p>
            {!editable && (
              <p className="mt-2 text-xs text-slate-500" data-testid="ai-managed">
                {aiStatus?.managedBy === 'vercel'
                  ? 'Provider configuration is managed by the server environment (Vercel project → Settings → Environment Variables: AI_PROVIDER, AI_MODEL and the provider key). It cannot be changed from the browser.'
                  : 'Provider configuration is managed by server environment variables (AI_PROVIDER, AI_MODEL, …). Change them on the server.'}
              </p>
            )}
            {editable && (
              <div className="mt-3 space-y-2">
                {Object.entries(LABELS).map(([value, label]) => (
                  <label key={value} className="flex items-center gap-2 text-sm text-slate-700">
                    <input type="radio" name="provider" checked={provider === value} onChange={() => setProvider(value)} />{label}
                  </label>
                ))}
                {provider === 'local' ? (
                  <input className={inputClass} placeholder="http://localhost:11434/v1" value={baseUrl} onChange={e => setBaseUrl(e.target.value)} aria-label="Local server URL" />
                ) : (
                  <input className={inputClass} type="password" autoComplete="off" value={apiKey} onChange={e => setApiKey(e.target.value)} aria-label="API key"
                    placeholder={aiStatus?.hasApiKey && aiStatus.provider === provider ? 'Leave blank to keep the key stored on the server' : 'API key'} />
                )}
                <input className={inputClass} placeholder={MODEL_HINTS[provider]} value={model} onChange={e => setModel(e.target.value)} aria-label="Model" />
                <p className="text-xs text-slate-500">
                  Keys are sent once to the local Python server and stored there (owner-only file) — never in this browser, chat, logs or
                  generated resumes. When you tailor, your profile and the job description are sent to the chosen provider.
                </p>
                <div className="flex gap-2">
                  <Button variant="primary" onClick={save} disabled={!model.trim()}>{aiStatus?.configured ? 'Update' : 'Connect'}</Button>
                  {aiStatus?.configured && aiStatus.source === 'file' && <Button variant="reject" onClick={actions.clearAISettings}>Disconnect</Button>}
                  {saved && <span className="text-xs text-emerald-700 self-center">{saved}</span>}
                </div>
              </div>
            )}
          </>
        )}
      </Card>

      <Card title="Local data">
        <p className="text-xs text-slate-500 mb-2">Your profile, current job and session are saved in this browser (never API keys).</p>
        <Button variant="reject" onClick={() => window.confirm('Clear the saved profile, job and session from this browser?') && actions.resetWorkspace()}>Clear saved Resume AI data</Button>
      </Card>
    </div>
  );
}
