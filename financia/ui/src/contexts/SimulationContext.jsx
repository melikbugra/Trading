import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { useWebSocket } from './WebSocketContext';

const SimulationContext = createContext(null);

export const useSimulation = () => useContext(SimulationContext);

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const SimulationProvider = ({ children }) => {
    // Simulation state
    const [isSimulationMode, setIsSimulationMode] = useState(false);
    const [isStatusLoaded, setIsStatusLoaded] = useState(false); // Track if initial status is loaded
    const [simStatus, setSimStatus] = useState({
        is_active: false,
        is_paused: false,
        day_completed: false,
        is_eod_running: false,
        is_scanning: false,
        hour_completed: false,
        current_time: null,
        start_date: null,
        end_date: null,
        seconds_per_hour: 30,
        session_id: null,
        // Balance fields
        initial_balance: 100000,
        current_balance: 100000,
        total_profit: 0,
        profit_percent: 0,
        total_trades: 0,
        winning_trades: 0,
        losing_trades: 0,
        win_rate: 0,
    });
    const [simSignals, setSimSignals] = useState([]);
    const [simEodResults, setSimEodResults] = useState(null); // EOD analysis results
    const [simEodProgress, setSimEodProgress] = useState(null); // EOD analysis progress
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState(null);
    const [backtestProgress, setBacktestProgress] = useState(null); // Backtest progress
    const [backtestResults, setBacktestResults] = useState(null); // Backtest summary results

    const { lastMessage } = useWebSocket();

    // Handle WebSocket messages for simulation
    useEffect(() => {
        if (!lastMessage) return;

        if (lastMessage.type === 'sim_status') {
            setSimStatus(lastMessage.data);
            setIsSimulationMode(lastMessage.data.is_active);
        } else if (lastMessage.type === 'sim_signals_update') {
            setSimSignals(lastMessage.data);
        } else if (lastMessage.type === 'sim_eod_progress') {
            // EOD progress update
            console.log('[Simulation] EOD progress:', lastMessage.data);
            // Clear progress if status is completed or cancelled
            if (lastMessage.data.status === 'completed' || lastMessage.data.status === 'cancelled') {
                setSimEodProgress(null);
            } else {
                setSimEodProgress(lastMessage.data);
            }
        } else if (lastMessage.type === 'sim_eod_complete') {
            // EOD completed notification with results
            console.log('[Simulation] EOD complete:', lastMessage.data);
            setSimEodResults(lastMessage.data);
            setSimEodProgress(null); // Clear progress on completion
        } else if (lastMessage.type === 'sim_backtest_progress') {
            setBacktestProgress(lastMessage.data);
        } else if (lastMessage.type === 'backtest_complete') {
            console.log('[Backtest] Complete:', lastMessage.data);
            setBacktestResults(lastMessage.data);
            setBacktestProgress(null);
        }
    }, [lastMessage]);

    // Fallback: If backtest is active, progress is gone, and no results yet, fetch from API
    useEffect(() => {
        if (
            simStatus.is_backtest &&
            simStatus.is_active &&
            !backtestProgress &&
            !backtestResults &&
            !isLoading
        ) {
            // Progress was cleared but no results arrived — try fetching from API
            const timer = setTimeout(async () => {
                try {
                    console.log('[Backtest] Fallback: fetching results from API...');
                    const res = await fetch(`${API_URL}/simulation/backtest/summary`);
                    if (res.ok) {
                        const data = await res.json();
                        if (data && data.overall && data.overall.total_trades > 0) {
                            console.log('[Backtest] Fallback: got results from API');
                            setBacktestResults(data);
                        }
                    }
                } catch (err) {
                    console.error('[Backtest] Fallback fetch failed:', err);
                }
            }, 3000); // Wait 3 seconds before fallback
            return () => clearTimeout(timer);
        }
    }, [simStatus.is_backtest, simStatus.is_active, backtestProgress, backtestResults, isLoading]);

    // Fetch initial simulation status on mount
    useEffect(() => {
        fetchStatus();
    }, []);

    const fetchStatus = async () => {
        try {
            const res = await fetch(`${API_URL}/simulation/status`);
            if (res.ok) {
                const data = await res.json();
                setSimStatus(data);
                setIsSimulationMode(data.is_active);
            }
        } catch (err) {
            console.error('[Simulation] Failed to fetch status:', err);
        } finally {
            setIsStatusLoaded(true); // Mark as loaded even on error
        }
    };

    const startSimulation = async (startDate, endDate, secondsPerHour, initialBalance = 100000) => {
        setIsLoading(true);
        setError(null);
        try {
            const res = await fetch(`${API_URL}/simulation/start`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    start_date: startDate,
                    end_date: endDate,
                    seconds_per_hour: secondsPerHour,
                    initial_balance: initialBalance,
                }),
            });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || 'Failed to start simulation');
            }
            const data = await res.json();
            setSimStatus(data);
            setIsSimulationMode(true);
            return data;
        } catch (err) {
            setError(err.message);
            throw err;
        } finally {
            setIsLoading(false);
        }
    };

    const pauseSimulation = async () => {
        setIsLoading(true);
        try {
            const res = await fetch(`${API_URL}/simulation/pause`, { method: 'POST' });
            if (res.ok) {
                const data = await res.json();
                setSimStatus(data);
            }
        } catch (err) {
            console.error('[Simulation] Pause failed:', err);
        } finally {
            setIsLoading(false);
        }
    };

    const resumeSimulation = async () => {
        setIsLoading(true);
        try {
            const res = await fetch(`${API_URL}/simulation/resume`, { method: 'POST' });
            if (res.ok) {
                const data = await res.json();
                setSimStatus(data);
            }
        } catch (err) {
            console.error('[Simulation] Resume failed:', err);
        } finally {
            setIsLoading(false);
        }
    };

    const nextHour = async () => {
        setIsLoading(true);
        try {
            const res = await fetch(`${API_URL}/simulation/next-hour`, { method: 'POST' });
            if (res.ok) {
                const data = await res.json();
                setSimStatus(data);
            }
        } catch (err) {
            console.error('[Simulation] Next hour failed:', err);
        } finally {
            setIsLoading(false);
        }
    };

    const nextDay = async () => {
        setIsLoading(true);
        try {
            const res = await fetch(`${API_URL}/simulation/next-day`, { method: 'POST' });
            if (res.ok) {
                const data = await res.json();
                setSimStatus(data);
                if (!data.is_active) {
                    setIsSimulationMode(false);
                }
            }
        } catch (err) {
            console.error('[Simulation] Next day failed:', err);
        } finally {
            setIsLoading(false);
        }
    };

    const stopSimulation = async () => {
        setIsLoading(true);
        try {
            const res = await fetch(`${API_URL}/simulation/stop`, { method: 'POST' });
            if (res.ok) {
                const data = await res.json();
                setSimStatus(data);
                setIsSimulationMode(false);
                setSimSignals([]);
                // Clear simulation EOD results from localStorage
                localStorage.removeItem('sim_eod_volume_results');
                localStorage.removeItem('sim_eod_trend_results');
            }
        } catch (err) {
            console.error('[Simulation] Stop failed:', err);
        } finally {
            setIsLoading(false);
        }
    };

    const cancelEodAnalysis = async () => {
        try {
            const res = await fetch(`${API_URL}/simulation/eod-analysis/cancel`, { method: 'POST' });
            if (res.ok) {
                setSimEodProgress(null);
                console.log('[Simulation] EOD analysis cancelled');
            }
        } catch (err) {
            console.error('[Simulation] Cancel EOD failed:', err);
        }
    };

    const startBacktest = async (startDate, endDate, initialBalance, strategyTypes) => {
        setIsLoading(true);
        setError(null);
        setBacktestResults(null);
        setBacktestProgress(null);
        try {
            const res = await fetch(`${API_URL}/simulation/backtest/start`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    start_date: startDate,
                    end_date: endDate,
                    initial_balance: initialBalance,
                    strategy_types: strategyTypes,
                }),
            });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || 'Failed to start backtest');
            }
            const data = await res.json();
            setSimStatus(data);
            setIsSimulationMode(true);
            return data;
        } catch (err) {
            setError(err.message);
            throw err;
        } finally {
            setIsLoading(false);
        }
    };

    const stopBacktest = async () => {
        setIsLoading(true);
        try {
            const res = await fetch(`${API_URL}/simulation/backtest/stop`, { method: 'POST' });
            if (res.ok) {
                const data = await res.json();
                setSimStatus(data);
                if (!data.is_active) {
                    setIsSimulationMode(false);
                }
                setBacktestProgress(null);
            }
        } catch (err) {
            console.error('[Backtest] Stop failed:', err);
        } finally {
            setIsLoading(false);
        }
    };

    const clearBacktestResults = () => {
        setBacktestResults(null);
    };

    // Helper to get API URL with simulation prefix
    const getApiUrl = useCallback((path) => {
        if (isSimulationMode) {
            // Redirect strategies endpoints to simulation
            if (path.startsWith('/strategies/signals')) {
                return `${API_URL}/simulation/signals${path.replace('/strategies/signals', '')}`;
            }
            if (path.startsWith('/strategies/trades')) {
                return `${API_URL}/simulation/trades${path.replace('/strategies/trades', '')}`;
            }
            if (path.startsWith('/strategies/chart-data')) {
                return `${API_URL}/simulation/chart-data${path.replace('/strategies/chart-data', '')}`;
            }
        }
        return `${API_URL}${path}`;
    }, [isSimulationMode]);

    // Format simulation time for display
    const formatSimTime = (isoString) => {
        if (!isoString) return '';
        const date = new Date(isoString);
        return date.toLocaleString('tr-TR', {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            weekday: 'long',
        });
    };

    // Get speed label
    const getSpeedLabel = (seconds) => {
        const labels = {
            10: 'Hızlı (10sn)',
            30: 'Normal (30sn)',
            60: 'Yavaş (60sn)',
            120: 'Çok Yavaş (120sn)',
        };
        return labels[seconds] || `${seconds}sn/saat`;
    };

    const value = {
        // State
        isSimulationMode,
        isStatusLoaded,
        simStatus,
        simSignals,
        simEodResults,
        simEodProgress,
        isLoading,
        error,
        backtestProgress,
        backtestResults,

        // Actions
        startSimulation,
        pauseSimulation,
        resumeSimulation,
        nextHour,
        nextDay,
        stopSimulation,
        cancelEodAnalysis,
        fetchStatus,
        startBacktest,
        stopBacktest,
        clearBacktestResults,

        // Helpers
        getApiUrl,
        formatSimTime,
        getSpeedLabel,
    };

    return (
        <SimulationContext.Provider value={value}>
            {children}
        </SimulationContext.Provider>
    );
};
