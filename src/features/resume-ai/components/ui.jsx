/** Small shared UI pieces for Resume AI, using Job Radar's existing Tailwind styles. */

import { X } from 'lucide-react';

export function Card({ title, icon: Icon, actions, children, className = '' }) {
  return (
    <section className={`bg-white rounded-lg border border-slate-200 ${className}`}>
      {(title || actions) && (
        <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            {Icon && <Icon className="w-4 h-4 text-slate-500" />}
            <h2 className="text-sm font-medium text-slate-700">{title}</h2>
          </div>
          {actions}
        </div>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

export function Button({ variant = 'secondary', className = '', ...props }) {
  const styles = {
    primary: 'bg-amber-500 text-white hover:bg-amber-600',
    secondary: 'bg-slate-100 text-slate-700 hover:bg-slate-200',
    dark: 'bg-slate-800 text-white hover:bg-slate-700',
    accept: 'bg-emerald-600 text-white hover:bg-emerald-700',
    reject: 'bg-red-50 text-red-700 hover:bg-red-100 border border-red-200',
    ghost: 'text-slate-600 hover:text-slate-800 hover:bg-slate-100'
  };
  return (
    <button
      type="button"
      className={`inline-flex items-center justify-center gap-1 px-3 py-1.5 text-sm font-medium rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${styles[variant]} ${className}`}
      {...props}
    />
  );
}

export function Chip({ tone = 'slate', children }) {
  const tones = {
    slate: 'bg-slate-100 text-slate-600',
    green: 'bg-emerald-50 text-emerald-700',
    red: 'bg-red-50 text-red-700',
    amber: 'bg-amber-50 text-amber-700',
    sky: 'bg-sky-50 text-sky-700'
  };
  return <span className={`px-2 py-0.5 text-xs rounded-full ${tones[tone]}`}>{children}</span>;
}

export const STATUS_TONES = { pending: 'slate', accepted: 'green', edited: 'sky', rejected: 'red' };

export function Modal({ title, onClose, children, footer }) {
  return (
    <div className="fixed inset-0 z-50 overflow-y-auto" role="dialog" aria-modal="true" aria-label={title}>
      <div className="flex min-h-full items-center justify-center p-4">
        <div className="fixed inset-0 bg-black/50" onClick={onClose} />
        <div className="relative bg-white rounded-xl shadow-xl max-w-lg w-full">
          <div className="px-5 py-3 border-b border-slate-200 flex items-center justify-between">
            <h2 className="text-base font-semibold text-slate-900">{title}</h2>
            <button type="button" onClick={onClose} className="p-1 text-slate-400 hover:text-slate-600" aria-label="Close">
              <X className="w-5 h-5" />
            </button>
          </div>
          <div className="p-5 text-sm text-slate-700">{children}</div>
          {footer && <div className="px-5 py-3 border-t border-slate-100 flex flex-wrap justify-end gap-2">{footer}</div>}
        </div>
      </div>
    </div>
  );
}

export const inputClass =
  'w-full px-3 py-2 text-sm border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent';
