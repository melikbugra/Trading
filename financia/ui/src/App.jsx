import { useState, useEffect } from 'react';
import PinLogin from './components/PinLogin';
import StrategyDashboard from './components/StrategyDashboard';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('signals');

  useEffect(() => {
    // Check localStorage for existing session
    const token = localStorage.getItem("auth_token");
    if (token === "valid") {
      setIsAuthenticated(true);
    }
    // Restore last active tab
    const savedTab = localStorage.getItem("active_tab");
    if (savedTab) {
      setActiveTab(savedTab);
    }
    setLoading(false);
  }, []);

  const handleTabChange = (tab) => {
    setActiveTab(tab);
    localStorage.setItem("active_tab", tab);
  };

  if (loading) return <div className="min-h-screen bg-black" />; // Prevent flash

  if (!isAuthenticated) {
    return <PinLogin onLogin={() => setIsAuthenticated(true)} />;
  }

  return (
    <div className="min-h-screen bg-terminal-dark">
      {/* Navigation Tabs */}
      <div className="bg-gray-900 border-b border-gray-800">
        <div className="max-w-6xl mx-auto px-8">
          <div className="flex gap-1">
            <button
              onClick={() => handleTabChange('signals')}
              className={`px-6 py-3 font-bold text-sm transition-colors border-b-2 ${activeTab === 'signals'
                ? 'border-green-500 text-green-400 bg-gray-800/50'
                : 'border-transparent text-gray-500 hover:text-gray-300 hover:bg-gray-800/30'
                }`}
            >
              🎯 Sinyaller
            </button>
            <button
              onClick={() => handleTabChange('strategies')}
              className={`px-6 py-3 font-bold text-sm transition-colors border-b-2 ${activeTab === 'strategies'
                ? 'border-purple-500 text-purple-400 bg-gray-800/50'
                : 'border-transparent text-gray-500 hover:text-gray-300 hover:bg-gray-800/30'
                }`}
            >
              ⚙️ Stratejiler
            </button>
            <button
              onClick={() => handleTabChange('eod')}
              className={`px-6 py-3 font-bold text-sm transition-colors border-b-2 ${activeTab === 'eod'
                ? 'border-blue-500 text-blue-400 bg-gray-800/50'
                : 'border-transparent text-gray-500 hover:text-gray-300 hover:bg-gray-800/30'
                }`}
            >
              🌙 Gün Sonu
            </button>
            <button
              onClick={() => handleTabChange('history')}
              className={`px-6 py-3 font-bold text-sm transition-colors border-b-2 ${activeTab === 'history'
                ? 'border-yellow-500 text-yellow-400 bg-gray-800/50'
                : 'border-transparent text-gray-500 hover:text-gray-300 hover:bg-gray-800/30'
                }`}
            >
              📊 Geçmiş
            </button>
          </div>
        </div>
      </div>

      {/* Dashboard with tab context */}
      <StrategyDashboard activeTab={activeTab} />
    </div>
  )
}

export default App

