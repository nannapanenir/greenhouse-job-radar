import { ExternalLink } from 'lucide-react';

const PORTFOLIO_URL = 'https://nannapanenir.github.io/rportfolio-website/';

export default function Footer() {
  const currentYear = new Date().getFullYear();

  return (
    <footer className="bg-white border-t border-slate-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-2 text-center sm:text-left">
          <p className="text-sm text-slate-500">
            Designed &amp; Developed by{' '}
            <a
              href={PORTFOLIO_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-amber-500 hover:text-amber-600 hover:underline cursor-pointer transition-colors duration-150"
            >
              Ramgopal Nannapaneni
              <ExternalLink className="w-3.5 h-3.5" />
            </a>
          </p>
          <p className="text-sm text-slate-500">
            &copy; {currentYear} AI Job Radar. All rights reserved.
          </p>
        </div>
      </div>
    </footer>
  );
}
