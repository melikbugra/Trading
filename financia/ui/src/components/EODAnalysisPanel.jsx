import { useState, useEffect, useCallback, useRef } from 'react';
import ChartModal from './ChartModal';
import { useToast } from '../contexts/ToastContext';
import { useWebSocket } from '../contexts/WebSocketContext';
import { useSimulation } from '../contexts/SimulationContext';

const API_BASE = import.meta.env.VITE_API_BASE || '';

export default function EODAnalysisPanel({ strategies }) {
    const { addToast } = useToast();
    const { eodStatus, eodProgress } = useWebSocket();
    const { isSimulationMode, simEodResults, simEodProgress, cancelEodAnalysis } = useSimulation();

    // Tab state
    const [activeTab, setActiveTab] = useState('volume'); // 'volume' or 'trend'

    // Volume analysis state
    const [volumeResults, setVolumeResults] = useState([]);
    const [volumeLoading, setVolumeLoading] = useState(false);
    const [volumeStats, setVolumeStats] = useState({ count: 0, total_scanned: 0 });
    const [volumeSortBy, setVolumeSortBy] = useState('change_percent');
    const [volumeSortDir, setVolumeSortDir] = useState('desc');
    const [volumeFilters, setVolumeFilters] = useState({
        min_change: 0,
        min_relative_volume: 1.5,
        min_volume: 50000000,
    });

    // Trend analysis state
    const [trendResults, setTrendResults] = useState([]);
    const [trendLoading, setTrendLoading] = useState(false);
    const [trendStats, setTrendStats] = useState({ count: 0, total_scanned: 0 });
    const [trendSortBy, setTrendSortBy] = useState('trend_score');
    const [trendSortDir, setTrendSortDir] = useState('desc');
    const [trendFilters, setTrendFilters] = useState({
        min_trend_score: 60,
        min_volume_tl: 50000000,
    });

    // Common state
    const [lastRun, setLastRun] = useState(null);
    const [chartModal, setChartModal] = useState(null);
    const [addToStrategyModal, setAddToStrategyModal] = useState(null);
    const [addingToStrategy, setAddingToStrategy] = useState(false);
    const [selectedStrategies, setSelectedStrategies] = useState([]); // For multi-select
    const prevAnalyzingRef = useRef(false);

    // Simulation strategies (loaded separately when in sim mode)
    const [simStrategies, setSimStrategies] = useState([]);

    // Reset selected strategies when modal opens
    useEffect(() => {
        if (addToStrategyModal) {
            setSelectedStrategies([]);
        }
    }, [addToStrategyModal]);

    // Load simulation strategies when modal opens in sim mode
    useEffect(() => {
        if (isSimulationMode && addToStrategyModal) {
            const loadSimStrategies = async () => {
                try {
                    const res = await fetch(`${API_BASE}/simulation/strategies`);
                    if (res.ok) {
                        const data = await res.json();
                        setSimStrategies(data);
                    }
                } catch (err) {
                    console.error('Failed to load sim strategies:', err);
                }
            };
            loadSimStrategies();
        }
    }, [isSimulationMode, addToStrategyModal]);

    // Get the right strategies list based on mode
    const activeStrategies = isSimulationMode ? simStrategies : strategies;

    // Load initial status on mount
    useEffect(() => {
        const loadInitialStatus = async () => {
            // First check localStorage for simulation results
            if (isSimulationMode) {
                const savedVolume = localStorage.getItem('sim_eod_volume_results');
                const savedTrend = localStorage.getItem('sim_eod_trend_results');

                if (savedVolume) {
                    try {
                        const data = JSON.parse(savedVolume);
                        const results = Array.isArray(data.results) ? data.results : [];
                        setVolumeResults(results);
                        setVolumeStats({ count: data.count || results.length, total_scanned: data.total_scanned || 0 });
                    } catch (e) {
                        console.error('Failed to parse saved volume results:', e);
                        localStorage.removeItem('sim_eod_volume_results');
                    }
                }

                if (savedTrend) {
                    try {
                        const data = JSON.parse(savedTrend);
                        // Ensure trend_score exists on each result
                        const results = Array.isArray(data.results) ? data.results.filter(r => r && typeof r.trend_score === 'number') : [];
                        setTrendResults(results);
                        setTrendStats({ count: data.count || results.length, total_scanned: data.total_scanned || 0 });
                    } catch (e) {
                        console.error('Failed to parse saved trend results:', e);
                        localStorage.removeItem('sim_eod_trend_results');
                    }
                }
                return;
            }

            try {
                const res = await fetch(`${API_BASE}/strategies/eod-analysis/status`);
                if (res.ok) {
                    const data = await res.json();

                    if (data.is_analyzing) {
                        setVolumeLoading(true);
                        setTrendLoading(true);
                        prevAnalyzingRef.current = true;
                    }

                    // Load volume results
                    if (data.last_results && data.last_results.length > 0) {
                        setVolumeResults(data.last_results);
                        setVolumeStats({ count: data.last_results_count, total_scanned: data.total_scanned });
                    }

                    // Load trend results
                    if (data.trend_results && data.trend_results.length > 0) {
                        setTrendResults(data.trend_results);
                        setTrendStats({ count: data.trend_results_count, total_scanned: data.total_scanned });
                    }

                    if (data.last_run_at) {
                        setLastRun(new Date(data.last_run_at));
                    }
                }
            } catch (err) {
                console.error('Failed to load EOD status:', err);
            }
        };
        loadInitialStatus();
    }, [isSimulationMode]);

    // Handle simulation EOD results
    useEffect(() => {
        if (!isSimulationMode || !simEodResults) return;

        console.log('[EODPanel] Simulation EOD results:', simEodResults);

        const results = Array.isArray(simEodResults.results) ? simEodResults.results : [];

        // Set volume results
        setVolumeResults(results);
        setVolumeStats({
            count: simEodResults.results_count || results.length,
            total_scanned: simEodResults.total_scanned || 0
        });

        // For simulation, use the same results for trend (filtered differently)
        // In real implementation, trend would have different data
        // For now, simulate trend by adding trend_score based on change_percent
        const trendData = results
            .filter(r => r && typeof r.change_percent === 'number' && typeof r.relative_volume === 'number')
            .map(r => {
                const trendScore = Math.round(Math.min(100, Math.max(0, 50 + (r.change_percent || 0) * 5 + ((r.relative_volume || 1) - 1) * 10)));
                return {
                    ...r,
                    trend_score: trendScore,
                    direction: (r.change_percent || 0) > 0 ? 'bullish' : 'bearish',
                    five_day_change: (r.change_percent || 0) * 2.5, // Simulated
                    // Add simulated indicator values for display
                    rsi: Math.round(30 + Math.random() * 40), // 30-70 range
                    adx: Math.round(15 + Math.random() * 25), // 15-40 range
                    bb_position: Math.round(20 + Math.random() * 60), // 20-80 range
                };
            })
            .filter(r => r.trend_score >= 60);

        setTrendResults(trendData);
        setTrendStats({
            count: trendData.length,
            total_scanned: simEodResults.total_scanned || 0
        });

        setLastRun(new Date());
        setVolumeLoading(false);
        setTrendLoading(false);

        // Save to localStorage for persistence
        localStorage.setItem('sim_eod_volume_results', JSON.stringify({
            results: results,
            count: simEodResults.results_count || results.length,
            total_scanned: simEodResults.total_scanned || 0,
            date: simEodResults.date
        }));

        localStorage.setItem('sim_eod_trend_results', JSON.stringify({
            results: trendData,
            count: trendData.length,
            total_scanned: simEodResults.total_scanned || 0,
            date: simEodResults.date
        }));

        if (simEodResults.date) {
            addToast(`Simülasyon gün sonu analizi: ${simEodResults.date}`, 'success');
        }
    }, [isSimulationMode, simEodResults, addToast]);

    // Handle simulation EOD progress
    useEffect(() => {
        if (!isSimulationMode) return;

        if (simEodProgress) {
            // Set loading based on status
            if (simEodProgress.status === 'running' || simEodProgress.status === 'started') {
                setVolumeLoading(true);
                setTrendLoading(true);
            } else if (simEodProgress.status === 'completed' || simEodProgress.status === 'cancelled') {
                setVolumeLoading(false);
                setTrendLoading(false);
            }
        }
    }, [isSimulationMode, simEodProgress]);

    // Handle WebSocket updates (live mode)
    useEffect(() => {
        if (isSimulationMode) return; // Skip in simulation mode
        if (!eodStatus) return;

        setVolumeLoading(eodStatus.is_analyzing);
        setTrendLoading(eodStatus.is_analyzing);

        if (prevAnalyzingRef.current && !eodStatus.is_analyzing) {
            // Volume results
            if (eodStatus.results && eodStatus.results.length > 0) {
                setVolumeResults(eodStatus.results);
                setVolumeStats({ count: eodStatus.results_count, total_scanned: eodStatus.total_scanned });
            }
            // Trend results
            if (eodStatus.trend_results && eodStatus.trend_results.length > 0) {
                setTrendResults(eodStatus.trend_results);
                setTrendStats({ count: eodStatus.trend_results_count, total_scanned: eodStatus.total_scanned });
            }
            if (eodStatus.last_run_at) {
                setLastRun(new Date(eodStatus.last_run_at));
            }
            addToast('Analiz tamamlandı', 'success');
        }

        prevAnalyzingRef.current = eodStatus.is_analyzing;
    }, [eodStatus, addToast, isSimulationMode]);

    // Cancel live EOD analysis
    const cancelLiveEodAnalysis = async () => {
        try {
            const res = await fetch(`${API_BASE}/strategies/eod-analysis/cancel`, { method: 'POST' });
            if (res.ok) {
                addToast('Analiz iptal edildi', 'info');
            }
        } catch (err) {
            console.error('Failed to cancel EOD analysis:', err);
        }
    };

    // Get current progress data based on mode
    const currentProgress = isSimulationMode ? simEodProgress : eodProgress;
    const handleCancelAnalysis = isSimulationMode ? cancelEodAnalysis : cancelLiveEodAnalysis;

    // Run Volume Analysis
    const runVolumeAnalysis = useCallback(async () => {
        if (volumeLoading) return;

        setVolumeLoading(true);
        setVolumeResults([]);
        setVolumeStats({ count: 0, total_scanned: 0 });

        try {
            // Use simulation endpoint if in simulation mode
            if (isSimulationMode) {
                const res = await fetch(`${API_BASE}/simulation/eod-analysis`, {
                    method: 'POST',
                });

                if (res.ok) {
                    addToast('Simülasyon EOD analizi başlatıldı...', 'info');
                    // Don't set loading to false here - WebSocket progress will handle it
                } else {
                    const err = await res.json();
                    addToast(err.detail || 'Analiz başlatılamadı', 'error');
                    setVolumeLoading(false);
                }
                return;
            }

            const params = new URLSearchParams({
                min_change: volumeFilters.min_change,
                min_relative_volume: volumeFilters.min_relative_volume,
                min_volume: volumeFilters.min_volume,
            });

            const res = await fetch(`${API_BASE}/strategies/eod-analysis/start?${params}`, {
                method: 'POST',
            });

            if (res.ok) {
                const data = await res.json();
                if (data.status === 'already_running') {
                    addToast('Analiz zaten çalışıyor...', 'info');
                } else {
                    addToast('Hacim analizi başlatıldı...', 'info');
                }
            } else {
                addToast('Analiz başlatılamadı', 'error');
                setVolumeLoading(false);
            }
        } catch (err) {
            console.error('Failed to start volume analysis:', err);
            addToast('Bağlantı hatası', 'error');
            setVolumeLoading(false);
        }
    }, [volumeFilters, volumeLoading, addToast, isSimulationMode]);

    // Run Trend Analysis
    const runTrendAnalysis = useCallback(async () => {
        if (trendLoading) return;

        setTrendLoading(true);
        setTrendResults([]);
        setTrendStats({ count: 0, total_scanned: 0 });

        try {
            // Use simulation endpoint if in simulation mode (same as volume for now)
            if (isSimulationMode) {
                const res = await fetch(`${API_BASE}/simulation/eod-analysis`, {
                    method: 'POST',
                });

                if (res.ok) {
                    addToast('Simülasyon EOD analizi başlatıldı...', 'info');
                    // Don't set loading to false here - WebSocket progress will handle it
                } else {
                    const err = await res.json();
                    addToast(err.detail || 'Analiz başlatılamadı', 'error');
                    setTrendLoading(false);
                }
                return;
            }

            const params = new URLSearchParams({
                min_trend_score: trendFilters.min_trend_score,
                min_volume_tl: trendFilters.min_volume_tl,
            });

            const res = await fetch(`${API_BASE}/strategies/trend-analysis/start?${params}`, {
                method: 'POST',
            });

            if (res.ok) {
                const data = await res.json();
                if (data.status === 'already_running') {
                    addToast('Analiz zaten çalışıyor...', 'info');
                } else {
                    addToast('Trend analizi başlatıldı...', 'info');
                }
            } else {
                addToast('Analiz başlatılamadı', 'error');
                setTrendLoading(false);
            }
        } catch (err) {
            console.error('Failed to start trend analysis:', err);
            addToast('Bağlantı hatası', 'error');
            setTrendLoading(false);
        }
    }, [trendFilters, trendLoading, addToast, isSimulationMode]);

    // Sorting handlers
    const handleVolumeSort = (field) => {
        if (volumeSortBy === field) {
            setVolumeSortDir(volumeSortDir === 'desc' ? 'asc' : 'desc');
        } else {
            setVolumeSortBy(field);
            setVolumeSortDir('desc');
        }
    };

    const handleTrendSort = (field) => {
        if (trendSortBy === field) {
            setTrendSortDir(trendSortDir === 'desc' ? 'asc' : 'desc');
        } else {
            setTrendSortBy(field);
            setTrendSortDir('desc');
        }
    };

    // Sorted results
    const sortedVolumeResults = [...volumeResults].sort((a, b) => {
        const aVal = a[volumeSortBy];
        const bVal = b[volumeSortBy];
        return volumeSortDir === 'desc' ? bVal - aVal : aVal - bVal;
    });

    const sortedTrendResults = [...trendResults].sort((a, b) => {
        const aVal = a[trendSortBy];
        const bVal = b[trendSortBy];
        return trendSortDir === 'desc' ? bVal - aVal : aVal - bVal;
    });

    // Helpers
    const openChartModal = (result) => {
        setChartModal({ ticker: result.ticker, market: 'bist100' });
    };

    const openAddToStrategyModal = (result) => {
        setAddToStrategyModal(result);
    };

    const toggleStrategySelection = (strategyId) => {
        setSelectedStrategies(prev =>
            prev.includes(strategyId)
                ? prev.filter(id => id !== strategyId)
                : [...prev, strategyId]
        );
    };

    const toggleAllStrategies = () => {
        const activeStrategyIds = activeStrategies.filter(s => s.is_active).map(s => s.id);
        if (selectedStrategies.length === activeStrategyIds.length) {
            setSelectedStrategies([]);
        } else {
            setSelectedStrategies(activeStrategyIds);
        }
    };

    const addToSelectedStrategies = async () => {
        if (!addToStrategyModal || selectedStrategies.length === 0) return;

        setAddingToStrategy(true);
        let successCount = 0;
        let errorCount = 0;

        try {
            // Use simulation endpoint if in simulation mode
            const endpoint = isSimulationMode
                ? `${API_BASE}/simulation/watchlist`
                : `${API_BASE}/strategies/watchlist`;

            for (const strategyId of selectedStrategies) {
                try {
                    const res = await fetch(endpoint, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            ticker: addToStrategyModal.ticker,
                            market: 'bist100',
                            strategy_id: strategyId,
                        }),
                    });

                    if (res.ok) {
                        successCount++;
                    } else {
                        errorCount++;
                    }
                } catch {
                    errorCount++;
                }
            }

            if (successCount > 0) {
                addToast(`${addToStrategyModal.symbol} ${successCount} stratejiye eklendi`, 'success');
            }
            if (errorCount > 0) {
                addToast(`${errorCount} strateji eklenemedi`, 'error');
            }
            setAddToStrategyModal(null);
        } catch (err) {
            console.error('Failed to add to strategies:', err);
            addToast('Bağlantı hatası', 'error');
        } finally {
            setAddingToStrategy(false);
        }
    };

    const formatVolume = (vol) => {
        if (vol >= 1_000_000_000) return `${(vol / 1_000_000_000).toFixed(1)}B`;
        if (vol >= 1_000_000) return `${(vol / 1_000_000).toFixed(1)}M`;
        if (vol >= 1_000) return `${(vol / 1_000).toFixed(1)}K`;
        return vol.toString();
    };

    const SortIcon = ({ field, currentSort, currentDir }) => {
        if (currentSort !== field) return <span className="text-gray-600">↕</span>;
        return currentDir === 'desc' ? <span className="text-blue-400">↓</span> : <span className="text-blue-400">↑</span>;
    };

    const getScoreColor = (score) => {
        if (score >= 80) return 'text-green-400';
        if (score >= 60) return 'text-blue-400';
        if (score >= 40) return 'text-yellow-400';
        return 'text-red-400';
    };

    const getDirectionEmoji = (direction) => {
        if (direction === 'bullish') return '🟢';
        if (direction === 'neutral') return '🟡';
        return '🔴';
    };

    return (
        <div>
            {/* Header */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
                <div>
                    <h2 className="text-lg sm:text-xl font-bold text-white">Gün Sonu Analizi</h2>
                    <p className="text-gray-500 text-xs sm:text-sm">
                        {lastRun ? `Son: ${lastRun.toLocaleTimeString('tr-TR')}` : 'BIST hisselerini analiz edin'}
                    </p>
                </div>
            </div>

            {/* Tab Buttons */}
            <div className="flex gap-2 mb-4 border-b border-gray-800 pb-2">
                <button
                    onClick={() => setActiveTab('volume')}
                    className={`px-4 py-2 rounded-t-lg font-medium transition-colors ${activeTab === 'volume'
                        ? 'bg-purple-600 text-white'
                        : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                        }`}
                >
                    📊 Hacim Analizi
                    {volumeResults.length > 0 && (
                        <span className="ml-2 text-xs bg-purple-800 px-2 py-0.5 rounded">
                            {volumeResults.length}
                        </span>
                    )}
                </button>
                <button
                    onClick={() => setActiveTab('trend')}
                    className={`px-4 py-2 rounded-t-lg font-medium transition-colors ${activeTab === 'trend'
                        ? 'bg-green-600 text-white'
                        : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                        }`}
                >
                    🎯 Trend Tahmini
                    {trendResults.length > 0 && (
                        <span className="ml-2 text-xs bg-green-800 px-2 py-0.5 rounded">
                            {trendResults.length}
                        </span>
                    )}
                </button>
            </div>

            {/* Volume Analysis Tab */}
            {activeTab === 'volume' && (
                <div>
                    {/* Filters */}
                    <div className="bg-gray-900/50 border border-gray-800 rounded-lg p-3 sm:p-4 mb-4">
                        <div className="flex flex-col sm:flex-row sm:items-end gap-3 sm:gap-4">
                            <div className="flex-1 grid grid-cols-3 gap-3">
                                <div>
                                    <label className="block text-gray-500 text-xs mb-1">Min. Değişim (%)</label>
                                    <input
                                        type="number"
                                        step="0.1"
                                        value={volumeFilters.min_change}
                                        onChange={(e) => setVolumeFilters({ ...volumeFilters, min_change: parseFloat(e.target.value) || 0 })}
                                        className="w-full px-2 py-1.5 bg-gray-800 border border-gray-700 rounded text-white font-mono text-sm focus:border-purple-500 focus:outline-none"
                                    />
                                </div>
                                <div>
                                    <label className="block text-gray-500 text-xs mb-1">Min. Bağıl Hacim</label>
                                    <input
                                        type="number"
                                        step="0.1"
                                        value={volumeFilters.min_relative_volume}
                                        onChange={(e) => setVolumeFilters({ ...volumeFilters, min_relative_volume: parseFloat(e.target.value) || 0 })}
                                        className="w-full px-2 py-1.5 bg-gray-800 border border-gray-700 rounded text-white font-mono text-sm focus:border-purple-500 focus:outline-none"
                                    />
                                </div>
                                <div>
                                    <label className="block text-gray-500 text-xs mb-1">Min. Hacim</label>
                                    <input
                                        type="number"
                                        step="1000000"
                                        value={volumeFilters.min_volume}
                                        onChange={(e) => setVolumeFilters({ ...volumeFilters, min_volume: parseFloat(e.target.value) || 0 })}
                                        className="w-full px-2 py-1.5 bg-gray-800 border border-gray-700 rounded text-white font-mono text-sm focus:border-purple-500 focus:outline-none"
                                    />
                                </div>
                            </div>
                            <button
                                onClick={runVolumeAnalysis}
                                disabled={volumeLoading}
                                className={`px-4 py-2 font-bold rounded-lg transition-all flex items-center gap-2 text-sm whitespace-nowrap ${volumeLoading
                                    ? 'bg-yellow-600 text-white cursor-wait'
                                    : 'bg-purple-600 hover:bg-purple-500 text-white'
                                    }`}
                            >
                                {volumeLoading ? (
                                    <><span className="animate-spin">🔄</span> Taranıyor...</>
                                ) : (
                                    <>🔍 Analiz Et</>
                                )}
                            </button>
                            {/* Cancel button */}
                            {volumeLoading && currentProgress && currentProgress.status === 'running' && (
                                <button
                                    onClick={handleCancelAnalysis}
                                    className="px-3 py-2 font-bold rounded-lg bg-red-600 hover:bg-red-500 text-white text-sm whitespace-nowrap"
                                >
                                    ❌ İptal
                                </button>
                            )}
                        </div>

                        {/* Progress Bar */}
                        {volumeLoading && currentProgress && currentProgress.total > 0 && (
                            <div className="mt-3">
                                <div className="flex items-center justify-between text-xs text-gray-400 mb-1">
                                    <span>{currentProgress.ticker || '...'} taranıyor...</span>
                                    <span>{currentProgress.current} / {currentProgress.total} ({Math.round((currentProgress.current / currentProgress.total) * 100)}%)</span>
                                </div>
                                <div className="w-full bg-gray-800 rounded-full h-2.5">
                                    <div
                                        className="bg-purple-600 h-2.5 rounded-full transition-all duration-300"
                                        style={{ width: `${(currentProgress.current / currentProgress.total) * 100}%` }}
                                    ></div>
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Stats */}
                    {volumeStats.count > 0 && (
                        <div className="flex gap-2 mb-3 text-xs sm:text-sm">
                            <span className="text-green-400">{volumeStats.count} hisse bulundu</span>
                            <span className="text-gray-500">/ {volumeStats.total_scanned} taranan</span>
                        </div>
                    )}

                    {/* Results Table */}
                    {volumeResults.length === 0 ? (
                        <div className="bg-gray-900/50 border border-gray-800 rounded-lg p-8 text-center">
                            <div className="text-3xl mb-3">📊</div>
                            <div className="text-gray-400">Henüz analiz çalıştırılmadı</div>
                        </div>
                    ) : (
                        <div className="bg-gray-900/50 border border-gray-800 rounded-lg overflow-hidden">
                            <div className="overflow-x-auto">
                                <table className="w-full min-w-[500px]">
                                    <thead className="bg-gray-800/50">
                                        <tr>
                                            <th className="text-left px-3 py-2 text-gray-400 text-xs font-medium">Sembol</th>
                                            <th className="text-right px-3 py-2 text-gray-400 text-xs font-medium">Kapanış</th>
                                            <th
                                                className="text-right px-3 py-2 text-gray-400 text-xs font-medium cursor-pointer hover:text-white"
                                                onClick={() => handleVolumeSort('change_percent')}
                                            >
                                                Değişim <SortIcon field="change_percent" currentSort={volumeSortBy} currentDir={volumeSortDir} />
                                            </th>
                                            <th
                                                className="text-right px-3 py-2 text-gray-400 text-xs font-medium cursor-pointer hover:text-white"
                                                onClick={() => handleVolumeSort('relative_volume')}
                                            >
                                                Bağıl Hacim <SortIcon field="relative_volume" currentSort={volumeSortBy} currentDir={volumeSortDir} />
                                            </th>
                                            <th
                                                className="text-right px-3 py-2 text-gray-400 text-xs font-medium cursor-pointer hover:text-white hidden sm:table-cell"
                                                onClick={() => handleVolumeSort('volume_tl')}
                                            >
                                                Hacim (TL) <SortIcon field="volume_tl" currentSort={volumeSortBy} currentDir={volumeSortDir} />
                                            </th>
                                            <th className="text-center px-3 py-2 text-gray-400 text-xs font-medium">+</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {sortedVolumeResults.map((result) => (
                                            <tr key={result.ticker} className="border-t border-gray-800 hover:bg-gray-800/30">
                                                <td className="px-3 py-2">
                                                    <button
                                                        onClick={() => openChartModal(result)}
                                                        className="text-white font-mono font-bold hover:text-purple-400 transition-colors flex items-center gap-1 text-sm"
                                                    >
                                                        {result.symbol}
                                                        <span className="text-xs text-gray-500">📊</span>
                                                    </button>
                                                </td>
                                                <td className="px-3 py-2 text-right text-white font-mono text-sm">
                                                    {result.close.toFixed(2)}
                                                </td>
                                                <td className="px-3 py-2 text-right">
                                                    <span className={`font-bold text-sm ${result.change_percent >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                                        {result.change_percent >= 0 ? '+' : ''}{result.change_percent.toFixed(2)}%
                                                    </span>
                                                </td>
                                                <td className="px-3 py-2 text-right">
                                                    <span className={`font-mono text-sm ${result.relative_volume >= 3 ? 'text-yellow-400 font-bold' : result.relative_volume >= 2 ? 'text-blue-400' : 'text-gray-400'}`}>
                                                        {result.relative_volume.toFixed(1)}x
                                                    </span>
                                                </td>
                                                <td className="px-3 py-2 text-right text-gray-300 font-mono text-sm hidden sm:table-cell">
                                                    {formatVolume(result.volume_tl || result.volume)}
                                                </td>
                                                <td className="px-3 py-2 text-center">
                                                    <button
                                                        onClick={() => openAddToStrategyModal(result)}
                                                        className="px-2 py-1 bg-blue-600/20 hover:bg-blue-600/40 text-blue-400 rounded text-xs transition-colors"
                                                    >
                                                        + Ekle
                                                    </button>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* Trend Analysis Tab */}
            {activeTab === 'trend' && (
                <div>
                    {/* Filters */}
                    <div className="bg-gray-900/50 border border-gray-800 rounded-lg p-3 sm:p-4 mb-4">
                        <div className="flex flex-col sm:flex-row sm:items-end gap-3 sm:gap-4">
                            <div className="flex-1 grid grid-cols-2 gap-3">
                                <div>
                                    <label className="block text-gray-500 text-xs mb-1">Min. Trend Skoru (0-100)</label>
                                    <input
                                        type="number"
                                        min="0"
                                        max="100"
                                        value={trendFilters.min_trend_score}
                                        onChange={(e) => setTrendFilters({ ...trendFilters, min_trend_score: parseInt(e.target.value) || 0 })}
                                        className="w-full px-2 py-1.5 bg-gray-800 border border-gray-700 rounded text-white font-mono text-sm focus:border-green-500 focus:outline-none"
                                    />
                                </div>
                                <div>
                                    <label className="block text-gray-500 text-xs mb-1">Min. Hacim (TL)</label>
                                    <input
                                        type="number"
                                        step="1000000"
                                        value={trendFilters.min_volume_tl}
                                        onChange={(e) => setTrendFilters({ ...trendFilters, min_volume_tl: parseFloat(e.target.value) || 0 })}
                                        className="w-full px-2 py-1.5 bg-gray-800 border border-gray-700 rounded text-white font-mono text-sm focus:border-green-500 focus:outline-none"
                                    />
                                </div>
                            </div>
                            <button
                                onClick={runTrendAnalysis}
                                disabled={trendLoading}
                                className={`px-4 py-2 font-bold rounded-lg transition-all flex items-center gap-2 text-sm whitespace-nowrap ${trendLoading
                                    ? 'bg-yellow-600 text-white cursor-wait'
                                    : 'bg-green-600 hover:bg-green-500 text-white'
                                    }`}
                            >
                                {trendLoading ? (
                                    <><span className="animate-spin">🔄</span> Taranıyor...</>
                                ) : (
                                    <>🎯 Trend Analizi</>
                                )}
                            </button>
                            {/* Cancel button */}
                            {trendLoading && currentProgress && currentProgress.status === 'running' && (
                                <button
                                    onClick={handleCancelAnalysis}
                                    className="px-3 py-2 font-bold rounded-lg bg-red-600 hover:bg-red-500 text-white text-sm whitespace-nowrap"
                                >
                                    ❌ İptal
                                </button>
                            )}
                        </div>

                        {/* Progress Bar */}
                        {trendLoading && currentProgress && currentProgress.total > 0 && (
                            <div className="mt-3">
                                <div className="flex items-center justify-between text-xs text-gray-400 mb-1">
                                    <span>{currentProgress.ticker || '...'} taranıyor...</span>
                                    <span>{currentProgress.current} / {currentProgress.total} ({Math.round((currentProgress.current / currentProgress.total) * 100)}%)</span>
                                </div>
                                <div className="w-full bg-gray-800 rounded-full h-2.5">
                                    <div
                                        className="bg-green-600 h-2.5 rounded-full transition-all duration-300"
                                        style={{ width: `${(currentProgress.current / currentProgress.total) * 100}%` }}
                                    ></div>
                                </div>
                            </div>
                        )}

                        <p className="text-gray-600 text-xs mt-2">
                            💡 Günlük mumlarla ertesi günün trend potansiyelini tahmin eder (RSI, MACD, EMA, ADX, Hacim, BB, Stochastic)
                        </p>
                    </div>

                    {/* Stats */}
                    {trendStats.count > 0 && (
                        <div className="flex gap-2 mb-3 text-xs sm:text-sm">
                            <span className="text-green-400">{trendStats.count} aday bulundu</span>
                            <span className="text-gray-500">/ {trendStats.total_scanned} taranan</span>
                        </div>
                    )}

                    {/* Results Table */}
                    {trendResults.length === 0 ? (
                        <div className="bg-gray-900/50 border border-gray-800 rounded-lg p-8 text-center">
                            <div className="text-3xl mb-3">🎯</div>
                            <div className="text-gray-400">Henüz trend analizi çalıştırılmadı</div>
                            <div className="text-gray-600 text-xs mt-2">
                                Yarın için yüksek potansiyelli hisseleri bulmak için analizi başlatın
                            </div>
                        </div>
                    ) : (
                        <div className="bg-gray-900/50 border border-gray-800 rounded-lg overflow-hidden">
                            <div className="overflow-x-auto">
                                <table className="w-full min-w-[700px]">
                                    <thead className="bg-gray-800/50">
                                        <tr>
                                            <th className="text-left px-3 py-2 text-gray-400 text-xs font-medium">Sembol</th>
                                            <th
                                                className="text-center px-3 py-2 text-gray-400 text-xs font-medium cursor-pointer hover:text-white"
                                                onClick={() => handleTrendSort('trend_score')}
                                            >
                                                Trend Skoru <SortIcon field="trend_score" currentSort={trendSortBy} currentDir={trendSortDir} />
                                            </th>
                                            <th className="text-center px-3 py-2 text-gray-400 text-xs font-medium">Yön</th>
                                            <th className="text-right px-3 py-2 text-gray-400 text-xs font-medium">Kapanış</th>
                                            <th
                                                className="text-right px-3 py-2 text-gray-400 text-xs font-medium cursor-pointer hover:text-white"
                                                onClick={() => handleTrendSort('change_percent')}
                                            >
                                                Günlük <SortIcon field="change_percent" currentSort={trendSortBy} currentDir={trendSortDir} />
                                            </th>
                                            <th
                                                className="text-right px-3 py-2 text-gray-400 text-xs font-medium cursor-pointer hover:text-white"
                                                onClick={() => handleTrendSort('five_day_change')}
                                            >
                                                5 Gün <SortIcon field="five_day_change" currentSort={trendSortBy} currentDir={trendSortDir} />
                                            </th>
                                            <th
                                                className="text-right px-3 py-2 text-gray-400 text-xs font-medium cursor-pointer hover:text-white hidden md:table-cell"
                                                onClick={() => handleTrendSort('rsi')}
                                            >
                                                RSI <SortIcon field="rsi" currentSort={trendSortBy} currentDir={trendSortDir} />
                                            </th>
                                            <th
                                                className="text-right px-3 py-2 text-gray-400 text-xs font-medium cursor-pointer hover:text-white hidden md:table-cell"
                                                onClick={() => handleTrendSort('adx')}
                                            >
                                                ADX <SortIcon field="adx" currentSort={trendSortBy} currentDir={trendSortDir} />
                                            </th>
                                            <th
                                                className="text-right px-3 py-2 text-gray-400 text-xs font-medium cursor-pointer hover:text-white hidden lg:table-cell"
                                                onClick={() => handleTrendSort('bb_position')}
                                            >
                                                BB% <SortIcon field="bb_position" currentSort={trendSortBy} currentDir={trendSortDir} />
                                            </th>
                                            <th className="text-center px-3 py-2 text-gray-400 text-xs font-medium">+</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {sortedTrendResults.map((result) => (
                                            <tr key={result.ticker} className="border-t border-gray-800 hover:bg-gray-800/30">
                                                <td className="px-3 py-2">
                                                    <button
                                                        onClick={() => openChartModal(result)}
                                                        className="text-white font-mono font-bold hover:text-green-400 transition-colors flex items-center gap-1 text-sm"
                                                    >
                                                        {result.symbol}
                                                        <span className="text-xs text-gray-500">📊</span>
                                                    </button>
                                                </td>
                                                <td className="px-3 py-2 text-center">
                                                    <div className="flex items-center justify-center gap-2">
                                                        <div className="w-16 bg-gray-700 rounded-full h-2">
                                                            <div
                                                                className={`h-2 rounded-full ${(result.trend_score || 0) >= 80 ? 'bg-green-500' : (result.trend_score || 0) >= 60 ? 'bg-blue-500' : (result.trend_score || 0) >= 40 ? 'bg-yellow-500' : 'bg-red-500'}`}
                                                                style={{ width: `${result.trend_score || 0}%` }}
                                                            />
                                                        </div>
                                                        <span className={`font-bold text-sm ${getScoreColor(result.trend_score || 0)}`}>
                                                            {result.trend_score || 0}
                                                        </span>
                                                    </div>
                                                </td>
                                                <td className="px-3 py-2 text-center text-lg">
                                                    {getDirectionEmoji(result.direction)}
                                                </td>
                                                <td className="px-3 py-2 text-right text-white font-mono text-sm">
                                                    {(result.close || 0).toFixed(2)}
                                                </td>
                                                <td className="px-3 py-2 text-right">
                                                    <span className={`font-bold text-sm ${(result.change_percent || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                                        {(result.change_percent || 0) >= 0 ? '+' : ''}{(result.change_percent || 0).toFixed(2)}%
                                                    </span>
                                                </td>
                                                <td className="px-3 py-2 text-right">
                                                    <span className={`text-sm ${(result.five_day_change || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                                        {(result.five_day_change || 0) >= 0 ? '+' : ''}{(result.five_day_change || 0).toFixed(1)}%
                                                    </span>
                                                </td>
                                                <td className="px-3 py-2 text-right hidden md:table-cell">
                                                    <span className={`font-mono text-sm ${(result.rsi || 50) < 30 ? 'text-green-400' : (result.rsi || 50) > 70 ? 'text-red-400' : 'text-gray-400'}`}>
                                                        {(result.rsi || 50).toFixed(0)}
                                                    </span>
                                                </td>
                                                <td className="px-3 py-2 text-right hidden md:table-cell">
                                                    <span className={`font-mono text-sm ${(result.adx || 0) > 25 ? 'text-yellow-400' : 'text-gray-400'}`}>
                                                        {(result.adx || 0).toFixed(0)}
                                                    </span>
                                                </td>
                                                <td className="px-3 py-2 text-right hidden lg:table-cell">
                                                    <span className={`font-mono text-sm ${(result.bb_position || 50) < 30 ? 'text-green-400' : (result.bb_position || 50) > 70 ? 'text-red-400' : 'text-gray-400'}`}>
                                                        {result.bb_position || 50}%
                                                    </span>
                                                </td>
                                                <td className="px-3 py-2 text-center">
                                                    <button
                                                        onClick={() => openAddToStrategyModal(result)}
                                                        className="px-2 py-1 bg-green-600/20 hover:bg-green-600/40 text-green-400 rounded text-xs transition-colors"
                                                    >
                                                        + Ekle
                                                    </button>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    )}

                    {/* Legend */}
                    {trendResults.length > 0 && (
                        <div className="mt-4 p-3 bg-gray-900/30 border border-gray-800 rounded-lg">
                            <h4 className="text-xs font-bold text-gray-400 mb-2">📖 Göstergeler</h4>
                            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs text-gray-500">
                                <div><span className="text-green-400">RSI &lt;30</span> = Aşırı satım</div>
                                <div><span className="text-yellow-400">ADX &gt;25</span> = Güçlü trend</div>
                                <div><span className="text-green-400">BB &lt;30%</span> = Alt banda yakın</div>
                                <div><span className="text-green-400">🟢</span> Bullish / <span className="text-yellow-400">🟡</span> Neutral / <span className="text-red-400">🔴</span> Bearish</div>
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* Chart Modal */}
            {chartModal && (
                <ChartModal
                    ticker={chartModal.ticker}
                    market={chartModal.market}
                    onClose={() => setChartModal(null)}
                />
            )}

            {/* Add to Strategy Modal */}
            {addToStrategyModal && (
                <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
                    <div className="bg-gray-900 border border-gray-700 rounded-lg p-4 sm:p-6 w-full max-w-md max-h-[90vh] overflow-y-auto">
                        <h3 className="text-xl font-bold text-white mb-4">
                            Stratejilere Ekle
                        </h3>

                        <div className="mb-4">
                            <div className="text-gray-400 mb-2">
                                <span className="font-bold text-white">{addToStrategyModal.symbol}</span>
                                {' '}hangi stratejilere eklensin?
                            </div>
                            {addToStrategyModal.trend_score && (
                                <div className="text-sm text-gray-500">
                                    Trend Skoru: <span className={getScoreColor(addToStrategyModal.trend_score)}>{addToStrategyModal.trend_score}</span>
                                </div>
                            )}
                        </div>

                        {/* Select All Checkbox */}
                        {activeStrategies.filter(s => s.is_active).length > 0 && (
                            <label className="flex items-center gap-3 px-4 py-2 bg-gray-800/50 rounded-lg mb-2 cursor-pointer hover:bg-gray-700/50 transition-colors border border-gray-600">
                                <input
                                    type="checkbox"
                                    checked={selectedStrategies.length === activeStrategies.filter(s => s.is_active).length}
                                    onChange={toggleAllStrategies}
                                    className="w-5 h-5 rounded bg-gray-700 border-gray-600 text-blue-500 focus:ring-blue-500 focus:ring-offset-gray-900"
                                />
                                <span className="text-white font-medium">Tümünü Seç</span>
                                <span className="text-gray-400 text-sm ml-auto">
                                    ({selectedStrategies.length}/{activeStrategies.filter(s => s.is_active).length})
                                </span>
                            </label>
                        )}

                        <div className="space-y-2 max-h-60 overflow-y-auto mb-4">
                            {activeStrategies.filter(s => s.is_active).length === 0 ? (
                                <div className="text-gray-500 text-center py-4">
                                    Aktif strateji bulunamadı
                                </div>
                            ) : (
                                activeStrategies.filter(s => s.is_active).map(strategy => (
                                    <label
                                        key={strategy.id}
                                        className={`flex items-center gap-3 px-4 py-3 rounded-lg cursor-pointer transition-colors ${selectedStrategies.includes(strategy.id)
                                                ? 'bg-blue-900/30 border border-blue-500/50'
                                                : 'bg-gray-800 hover:bg-gray-700 border border-transparent'
                                            }`}
                                    >
                                        <input
                                            type="checkbox"
                                            checked={selectedStrategies.includes(strategy.id)}
                                            onChange={() => toggleStrategySelection(strategy.id)}
                                            className="w-5 h-5 rounded bg-gray-700 border-gray-600 text-blue-500 focus:ring-blue-500 focus:ring-offset-gray-900"
                                        />
                                        <div className="flex-1">
                                            <div className="text-white font-medium">{strategy.name}</div>
                                            <div className="text-gray-500 text-sm">{strategy.strategy_type}</div>
                                        </div>
                                    </label>
                                ))
                            )}
                        </div>

                        <div className="flex gap-2">
                            <button
                                onClick={() => setAddToStrategyModal(null)}
                                className="flex-1 px-4 py-3 bg-gray-700 hover:bg-gray-600 text-white rounded transition-colors"
                            >
                                İptal
                            </button>
                            <button
                                onClick={addToSelectedStrategies}
                                disabled={addingToStrategy || selectedStrategies.length === 0}
                                className="flex-1 px-4 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:text-gray-500 text-white rounded transition-colors font-medium"
                            >
                                {addingToStrategy ? (
                                    <span className="flex items-center justify-center gap-2">
                                        <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                                        </svg>
                                        Ekleniyor...
                                    </span>
                                ) : (
                                    `Ekle (${selectedStrategies.length})`
                                )}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
