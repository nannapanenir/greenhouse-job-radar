import { useEffect, useRef, useState } from 'react';
import { Bot, Send } from 'lucide-react';
import { Card } from './ui';

const SUGGESTIONS = ['Analyze my fit.', 'Tailor my resume for this job.', 'What skills am I missing?', 'Show me what changed.'];

/** AI Assistant: messages map to controlled operations (see backend/resume/chat.py). */
export default function ResumeChat({ chatLog, busy, onSend }) {
  const [text, setText] = useState('');
  const log = useRef(null);

  useEffect(() => {
    if (log.current) log.current.scrollTop = log.current.scrollHeight;
  }, [chatLog, busy]);

  const submit = event => {
    event.preventDefault();
    if (!text.trim() || busy) return;
    onSend(text);
    setText('');
  };

  return (
    <Card title="AI Assistant" icon={Bot}>
      <div ref={log} className="h-72 overflow-y-auto space-y-2 pr-1" data-testid="chat-log" aria-live="polite">
        {chatLog.length === 0 && (
          <p className="text-sm text-slate-500">
            Ask things like “Focus more on Angular”, “Don't make me look backend-heavy”, “Make the summary shorter”,
            “Why did you change this bullet?” or “Generate the final resume”. You can also paste a job description here.
          </p>
        )}
        {chatLog.map((message, index) => (
          <div key={index} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[85%] rounded-lg px-3 py-2 text-sm whitespace-pre-wrap ${
              message.role === 'user' ? 'bg-amber-500 text-white' : 'bg-slate-100 text-slate-800'}`}>
              {message.text}
              <div className={`mt-1 text-[10px] ${message.role === 'user' ? 'text-amber-100' : 'text-slate-400'}`}>{message.time}</div>
            </div>
          </div>
        ))}
        {busy && <div className="text-xs text-slate-500 animate-pulse">{busy}</div>}
      </div>
      <div className="flex flex-wrap gap-1 mt-2">
        {SUGGESTIONS.map(s => (
          <button key={s} type="button" disabled={!!busy} onClick={() => onSend(s)}
            className="px-2 py-0.5 text-xs bg-slate-50 text-slate-600 rounded-full hover:bg-slate-100 disabled:opacity-50">{s}</button>
        ))}
      </div>
      <form onSubmit={submit} className="flex gap-2 mt-2">
        <input value={text} onChange={e => setText(e.target.value)} aria-label="Message"
          placeholder="Ask something or paste a job description…"
          className="flex-1 px-3 py-2 text-sm border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent" />
        <button type="submit" disabled={!text.trim() || !!busy} aria-label="Send"
          className="px-3 py-2 bg-amber-500 text-white rounded-md hover:bg-amber-600 disabled:opacity-50">
          <Send className="w-4 h-4" />
        </button>
      </form>
    </Card>
  );
}
