import { useState, useEffect } from 'react';
import StrategyDashboard from './StrategyDashboard';
import SimulationBanner from './SimulationBanner';
import SimulationPanel from './SimulationPanel';
import BacktestResultsModal from './BacktestResultsModal';
import { useSimulation } from '../contexts/SimulationContext';

// The intraday trading sub-app: the original tabbed shell, now reachable from
// the landing page. `onHome` returns to the landing page.
export default function TradingApp({ onHome }) {
  const [activeTab, setActiveTab] = useState('signals');
  const [showSimPanel, setShowSimPanel] = useState(false);
  const [showBacktestResults, setShowBacktestResults] = useState(false);

  const { isSimulationMode, backtestResults } = useSimulation();

  useEffect(() => {
    if (backtestResults) {
      setShowBacktestResults(true);
    }
  }, [backtestResults]);

  useEffect(() => {
    const savedTab = localStorage.getItem('active_tab');
    if (savedTab) setActiveTab(savedTab);
  }, []);

  const handleTabChange = (tab) => {
    setActiveTab(tab);
    localStorage.setItem('active_tab', tab);
  };

  return (
    <div className="min-h-screen bg-terminal-dark flex flex-col">
      {/* Simulation Banner - shown when simulation is active */}
      <SimulationBanner />

      {/* Navigation Tabs */}
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
            <button
              onClick={() => handleTabChange('signals')}
              className={`px-3 sm:px-6 py-3 font-bold text-xs sm:text-sm transition-colors border-b-2 whitespace-nowrap ${activeTab === 'signals'
                ? 'border-green-500 text-green-400 bg-gray-800/50'
                : 'border-transparent text-gray-500 hover:text-gray-300 hover:bg-gray-800/30'
                }`}
            >
              🎯 <span className="hidden xs:inline">Sinyaller</span><span className="xs:hidden">Sinyal</span>
            </button>
            <button
              onClick={() => handleTabChange('strategies')}
              className={`px-3 sm:px-6 py-3 font-bold text-xs sm:text-sm transition-colors border-b-2 whitespace-nowrap ${activeTab === 'strategies'
                ? 'border-purple-500 text-purple-400 bg-gray-800/50'
                : 'border-transparent text-gray-500 hover:text-gray-300 hover:bg-gray-800/30'
                }`}
            >
              ⚙️ <span className="hidden xs:inline">Stratejiler</span><span className="xs:hidden">Strateji</span>
            </button>
            <button
              onClick={() => handleTabChange('eod')}
              className={`px-3 sm:px-6 py-3 font-bold text-xs sm:text-sm transition-colors border-b-2 whitespace-nowrap ${activeTab === 'eod'
                ? 'border-blue-500 text-blue-400 bg-gray-800/50'
                : 'border-transparent text-gray-500 hover:text-gray-300 hover:bg-gray-800/30'
                }`}
            >
              🌙 <span className="hidden sm:inline">Gün Sonu</span><span className="sm:hidden">EOD</span>
            </button>
            <button
              onClick={() => handleTabChange('history')}
              className={`px-3 sm:px-6 py-3 font-bold text-xs sm:text-sm transition-colors border-b-2 whitespace-nowrap ${activeTab === 'history'
                ? 'border-yellow-500 text-yellow-400 bg-gray-800/50'
                : 'border-transparent text-gray-500 hover:text-gray-300 hover:bg-gray-800/30'
                }`}
            >
              📊 Geçmiş
            </button>

            {/* Simulation Button - only show when not in simulation */}
            {!isSimulationMode && (
              <button
                onClick={() => setShowSimPanel(true)}
                className="ml-auto px-3 sm:px-4 py-3 font-bold text-xs sm:text-sm transition-colors border-b-2 border-transparent text-gray-500 hover:text-purple-400 hover:bg-purple-500/10 whitespace-nowrap"
              >
                🎮 <span className="hidden sm:inline">Simülasyon</span>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Dashboard with tab context */}
      <StrategyDashboard activeTab={activeTab} />

      {/* Simulation Setup Panel */}
      {showSimPanel && (
        <SimulationPanel onClose={() => setShowSimPanel(false)} />
      )}

      {/* Backtest Results Modal */}
      {showBacktestResults && (
        <BacktestResultsModal
          onClose={() => setShowBacktestResults(false)}
          onGoToHistory={() => {
            setShowBacktestResults(false);
            handleTabChange('history');
          }}
        />
      )}
    </div>
  );
}
