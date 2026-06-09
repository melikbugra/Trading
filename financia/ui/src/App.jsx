import { useState, useEffect } from 'react';
import PinLogin from './components/PinLogin';
import LandingPage from './components/LandingPage';
import TradingApp from './components/TradingApp';
import InvestingApp from './components/InvestingApp';
import { SimulationProvider } from './contexts/SimulationContext';

function AppContent() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);
  // Top-level view: null = landing, 'trading', 'investing'
  const [appView, setAppView] = useState(null);

  useEffect(() => {
    // Check localStorage for existing session
    const token = localStorage.getItem("auth_token");
    if (token === "valid") {
      setIsAuthenticated(true);
    }
    // Restore last opened sub-app
    const savedView = localStorage.getItem("app_view");
    if (savedView === 'trading' || savedView === 'investing') {
      setAppView(savedView);
    }
    setLoading(false);
  }, []);

  const selectView = (view) => {
    setAppView(view);
    localStorage.setItem("app_view", view ?? "");
  };

  const goHome = () => {
    setAppView(null);
    localStorage.removeItem("app_view");
  };

  if (loading) return <div className="min-h-screen bg-black" />; // Prevent flash

  if (!isAuthenticated) {
    return <PinLogin onLogin={() => setIsAuthenticated(true)} />;
  }

  if (appView === 'trading') return <TradingApp onHome={goHome} />;
  if (appView === 'investing') return <InvestingApp onHome={goHome} />;
  return <LandingPage onSelect={selectView} />;
}

function App() {
  return (
    <SimulationProvider>
      <AppContent />
    </SimulationProvider>
  );
}

export default App
