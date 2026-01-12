import { useState, useEffect } from 'react';
import Dashboard from './components/Dashboard';
import PinLogin from './components/PinLogin';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Check localStorage for existing session
    const token = localStorage.getItem("auth_token");
    if (token === "valid") {
      setIsAuthenticated(true);
    }
    setLoading(false);
  }, []);

  if (loading) return <div className="min-h-screen bg-black" />; // Prevent flash

  if (!isAuthenticated) {
    return <PinLogin onLogin={() => setIsAuthenticated(true)} />;
  }

  return (
    <Dashboard />
  )
}

export default App
