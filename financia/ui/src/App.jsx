import { useState, useEffect } from 'react';
import Dashboard from './components/Dashboard';
import PinLogin from './components/PinLogin';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);
  const [activeMarket, setActiveMarket] = useState('bist100');

  useEffect(() => {
    // Check localStorage for existing session
    const token = localStorage.getItem("auth_token");
    if (token === "valid") {
      setIsAuthenticated(true);
    }
    // Restore last active market
    const savedMarket = localStorage.getItem("active_market");
    if (savedMarket) {
      setActiveMarket(savedMarket);
    }
    setLoading(false);
  }, []);

  const handleMarketChange = (market) => {
    setActiveMarket(market);
    localStorage.setItem("active_market", market);
  };

  if (loading) return <div className="min-h-screen bg-black" />; // Prevent flash

  if (!isAuthenticated) {
    return <PinLogin onLogin={() => setIsAuthenticated(true)} />;
  }

  return (
    <div className="min-h-screen bg-terminal-dark">
      {/* Market Tabs */}
      <div className="bg-gray-900 border-b border-gray-800">
        <div className="max-w-6xl mx-auto px-8">
          <div className="flex gap-1">
            <button
              onClick={() => handleMarketChange('bist100')}
              className={`px-6 py-3 font-bold text-sm transition-colors border-b-2 ${activeMarket === 'bist100'
                  ? 'border-green-500 text-green-400 bg-gray-800/50'
                  : 'border-transparent text-gray-500 hover:text-gray-300 hover:bg-gray-800/30'
                }`}
            >
              🇹🇷 BIST100
            </button>
            <button
              onClick={() => handleMarketChange('binance')}
              className={`px-6 py-3 font-bold text-sm transition-colors border-b-2 ${activeMarket === 'binance'
                  ? 'border-yellow-500 text-yellow-400 bg-gray-800/50'
                  : 'border-transparent text-gray-500 hover:text-gray-300 hover:bg-gray-800/30'
                }`}
            >
              ₿ Binance
            </button>
          </div>
        </div>
      </div>

      {/* Dashboard with market context */}
      <Dashboard market={activeMarket} key={activeMarket} />
    </div>
  )
}

export default App

