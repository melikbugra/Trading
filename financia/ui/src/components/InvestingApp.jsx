import { useState } from 'react';
import PortfolioPanel from './investing/PortfolioPanel';
import ScreenerPanel from './investing/ScreenerPanel';
import DividendCalendarPanel from './investing/DividendCalendarPanel';
import WatchlistPanel from './investing/WatchlistPanel';
import NewsPanel from './investing/NewsPanel';
import FundEtfPanel from './investing/FundEtfPanel';

const TABS = [
  { key: 'portfolio', label: '💼 Portföy', color: 'blue' },
  { key: 'screener', label: '🔎 Analiz & Tarayıcı', color: 'green' },
  { key: 'funds', label: '🧺 Fon & ETF', color: 'pink' },
  { key: 'news', label: '📰 Haberler', color: 'cyan' },
  { key: 'dividends', label: '💰 Temettü', color: 'yellow' },
  { key: 'watchlist', label: '⭐ İzleme', color: 'purple' },
];

const ACTIVE_CLS = {
  blue: 'border-blue-500 text-blue-400 bg-gray-800/50',
  green: 'border-green-500 text-green-400 bg-gray-800/50',
  cyan: 'border-cyan-500 text-cyan-400 bg-gray-800/50',
  yellow: 'border-yellow-500 text-yellow-400 bg-gray-800/50',
  purple: 'border-purple-500 text-purple-400 bg-gray-800/50',
  pink: 'border-pink-500 text-pink-400 bg-gray-800/50',
};

// The long-term investing sub-app shell.
export default function InvestingApp({ onHome }) {
  const [tab, setTab] = useState(() => {
    const saved = localStorage.getItem('invest_tab');
    return TABS.some((t) => t.key === saved) ? saved : 'portfolio';
  });

  const changeTab = (t) => {
    setTab(t);
    localStorage.setItem('invest_tab', t);
  };

  return (
    <div className="min-h-screen bg-terminal-dark flex flex-col">
      <div className="bg-gray-900 border-b border-gray-800">
        <div className="max-w-6xl mx-auto px-2 sm:px-8">
          <div className="flex items-center overflow-x-auto scrollbar-hide">
            <button
              onClick={onHome}
              className="px-2 sm:px-3 py-3 font-bold text-xs sm:text-sm text-gray-500 hover:text-white transition-colors whitespace-nowrap"
              title="Ana Sayfa"
            >
              ← <span className="hidden sm:inline">Ana Sayfa</span>
            </button>
            {TABS.map((t) => (
              <button
                key={t.key}
                onClick={() => changeTab(t.key)}
                className={`px-3 sm:px-6 py-3 font-bold text-xs sm:text-sm transition-colors border-b-2 whitespace-nowrap ${tab === t.key
                  ? ACTIVE_CLS[t.color]
                  : 'border-transparent text-gray-500 hover:text-gray-300 hover:bg-gray-800/30'
                  }`}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="flex-1 max-w-6xl w-full mx-auto px-2 sm:px-8 py-4">
        {tab === 'portfolio' && <PortfolioPanel />}
        {tab === 'screener' && <ScreenerPanel />}
        {tab === 'funds' && <FundEtfPanel />}
        {tab === 'news' && <NewsPanel />}
        {tab === 'dividends' && <DividendCalendarPanel />}
        {tab === 'watchlist' && <WatchlistPanel />}
      </div>
    </div>
  );
}
