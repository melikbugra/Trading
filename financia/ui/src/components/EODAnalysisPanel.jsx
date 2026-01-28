import { useState, useEffect, useCallback, useRef } from 'react';
import ChartModal from './ChartModal';
import { useToast } from '../contexts/ToastContext';
import { useWebSocket } from '../contexts/WebSocketContext';

const API_BASE = import.meta.env.VITE_API_BASE || '';

export default function EODAnalysisPanel({ strategies }) {
    const { addToast } = useToast();
    const { eodStatus } = useWebSocket();
    const [results, setResults] = useState([]);
    const [loading, setLoading] = useState(false);
    const [lastRun, setLastRun] = useState(null);
    const [stats, setStats] = useState({ count: 0, total_scanned: 0 });
    const [sortBy, setSortBy] = useState('change_percent'); // change_percent, relative_volume, volume_tl
    const [sortDir, setSortDir] = useState('desc');
    const [chartModal, setChartModal] = useState(null);
    const [addToStrategyModal, setAddToStrategyModal] = useState(null);
    const [addingToStrategy, setAddingToStrategy] = useState(false);
    const prevAnalyzingRef = useRef(false);

    // Filters
    const [filters, setFilters] = useState({
        min_change: 0,
        min_relative_volume: 1.5,
        min_volume: 50000000,
    });

    // Load last results on mount
    useEffect(() => {
        const loadInitialStatus = async () => {
            try {
                const res = await fetch(`${API_BASE}/strategies/eod-analysis/status`);
                if (res.ok) {
                    const data = await res.json();

                    // If analysis is running, set loading state
                    if (data.is_analyzing) {
                        setLoading(true);
                        prevAnalyzingRef.current = true;
                    }

                    // Load previous results if available
                    if (data.last_results && data.last_results.length > 0) {
                        setResults(data.last_results);
                        setStats({ count: data.last_results_count, total_scanned: data.total_scanned });
                        if (data.last_run_at) {
                            setLastRun(new Date(data.last_run_at));
                        }
                    }
                }
            } catch (err) {
                console.error('Failed to load EOD status:', err);
            }
        };
        loadInitialStatus();
    }, []);

    // Handle WebSocket updates for EOD status
    useEffect(() => {
        if (!eodStatus) return;

        // Update loading state from WebSocket
        setLoading(eodStatus.is_analyzing);

        // Check if analysis just completed (was analyzing, now not)
        if (prevAnalyzingRef.current && !eodStatus.is_analyzing) {
            // Analysis just completed
            if (eodStatus.results && eodStatus.results.length > 0) {
                setResults(eodStatus.results);
                setStats({ count: eodStatus.results_count, total_scanned: eodStatus.total_scanned });
                if (eodStatus.last_run_at) {
                    setLastRun(new Date(eodStatus.last_run_at));
                }
                addToast(`Analiz tamamlandı: ${eodStatus.results_count} hisse bulundu`, 'success');
            } else {
                addToast('Analiz tamamlandı: Sonuç bulunamadı', 'info');
            }
        }

        // Update ref for next comparison
        prevAnalyzingRef.current = eodStatus.is_analyzing;
    }, [eodStatus, addToast]);

    const runAnalysis = useCallback(async () => {
        if (loading) return; // Already running

        setLoading(true);
        setResults([]);  // Clear old results
        setStats({ count: 0, total_scanned: 0 });  // Reset stats

        try {
            const params = new URLSearchParams({
                min_change: filters.min_change,
                min_relative_volume: filters.min_relative_volume,
                min_volume: filters.min_volume,
            });

            // Start analysis asynchronously
            const res = await fetch(`${API_BASE}/strategies/eod-analysis/start?${params}`, {
                method: 'POST',
            });

            if (res.ok) {
                const data = await res.json();
                if (data.status === 'already_running') {
                    addToast('Analiz zaten çalışıyor...', 'info');
                } else {
                    addToast('Analiz başlatıldı...', 'info');
                }
                // WebSocket will handle the rest
            } else {
                addToast('Analiz başlatılamadı', 'error');
                setLoading(false);
            }
        } catch (err) {
            console.error('Failed to start EOD analysis:', err);
            addToast('Bağlantı hatası', 'error');
            setLoading(false);
        }
    }, [filters, loading, addToast]);

    const handleSort = (field) => {
        if (sortBy === field) {
            setSortDir(sortDir === 'desc' ? 'asc' : 'desc');
        } else {
            setSortBy(field);
            setSortDir('desc');
        }
    };

    const sortedResults = [...results].sort((a, b) => {
        const aVal = a[sortBy];
        const bVal = b[sortBy];
        return sortDir === 'desc' ? bVal - aVal : aVal - bVal;
    });

    const openChartModal = (result) => {
        setChartModal({
            ticker: result.ticker,
            market: 'bist100',
        });
    };

    const openAddToStrategyModal = (result) => {
        setAddToStrategyModal(result);
    };

    const addToStrategy = async (strategyId) => {
        if (!addToStrategyModal) return;

        setAddingToStrategy(true);
        try {
            const res = await fetch(`${API_BASE}/strategies/watchlist`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    ticker: addToStrategyModal.ticker,
                    market: 'bist100',
                    strategy_id: strategyId,
                }),
            });

            if (res.ok) {
                addToast(`${addToStrategyModal.symbol} stratejiye eklendi`, 'success');
                setAddToStrategyModal(null);
            } else {
                const err = await res.json();
                addToast(err.detail || 'Ekleme başarısız', 'error');
            }
        } catch (err) {
            console.error('Failed to add to strategy:', err);
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

    const SortIcon = ({ field }) => {
        if (sortBy !== field) return <span className="text-gray-600">↕</span>;
        return sortDir === 'desc' ? <span className="text-blue-400">↓</span> : <span className="text-blue-400">↑</span>;
    };

    return (
        <div>
            {/* Header with Run Button */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4 sm:mb-6">
                <div>
                    <h2 className="text-lg sm:text-xl font-bold text-white">Gün Sonu Analizi</h2>
                    <p className="text-gray-500 text-xs sm:text-sm">
                        BIST hisselerini filtreleyin
                    </p>
                </div>
                <div className="flex items-center gap-2 sm:gap-4">
                    {lastRun && (
                        <span className="text-gray-500 text-xs sm:text-sm hidden sm:inline">
                            Son: {lastRun.toLocaleTimeString('tr-TR')}
                        </span>
                    )}
                    <button
                        onClick={runAnalysis}
                        disabled={loading}
                        className={`px-4 sm:px-6 py-2 sm:py-3 font-bold rounded-lg transition-all flex items-center gap-2 text-sm sm:text-base ${
                            loading
                                ? 'bg-yellow-600 text-white cursor-wait'
                                : 'bg-purple-600 hover:bg-purple-500 text-white'
                        }`}
                    >
                        {loading ? (
                            <>
                                <span className="animate-spin">🔄</span>
                                <span className="hidden sm:inline">Taranıyor...</span>
                                <span className="sm:hidden">...</span>
                            </>
                        ) : (
                            <>
                                🔍 <span className="hidden sm:inline">Analizi </span>Çalıştır
                            </>
                        )}
                    </button>
                </div>
            </div>

            {/* Filters */}
            <div className="bg-gray-900/50 border border-gray-800 rounded-lg p-3 sm:p-4 mb-4 sm:mb-6">
                <h3 className="text-xs sm:text-sm font-bold text-gray-400 mb-2 sm:mb-3">Filtreler</h3>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-4">
                    <div>
                        <label className="block text-gray-500 text-xs mb-1">Min. Değişim (%)</label>
                        <input
                            type="number"
                            step="0.1"
                            value={filters.min_change}
                            onChange={(e) => setFilters({ ...filters, min_change: parseFloat(e.target.value) || 0 })}
                            className="w-full px-2 sm:px-3 py-1.5 sm:py-2 bg-gray-800 border border-gray-700 rounded text-white font-mono text-sm focus:border-purple-500 focus:outline-none"
                        />
                    </div>
                    <div>
                        <label className="block text-gray-500 text-xs mb-1">Min. Bağıl Hacim</label>
                        <input
                            type="number"
                            step="0.1"
                            value={filters.min_relative_volume}
                            onChange={(e) => setFilters({ ...filters, min_relative_volume: parseFloat(e.target.value) || 0 })}
                            className="w-full px-2 sm:px-3 py-1.5 sm:py-2 bg-gray-800 border border-gray-700 rounded text-white font-mono text-sm focus:border-purple-500 focus:outline-none"
                        />
                    </div>
                    <div>
                        <label className="block text-gray-500 text-xs mb-1">Min. Hacim ({formatVolume(filters.min_volume)})</label>
                        <input
                            type="number"
                            step="1000000"
                            value={filters.min_volume}
                            onChange={(e) => setFilters({ ...filters, min_volume: parseFloat(e.target.value) || 0 })}
                            className="w-full px-2 sm:px-3 py-1.5 sm:py-2 bg-gray-800 border border-gray-700 rounded text-white font-mono text-sm focus:border-purple-500 focus:outline-none"
                        />
                    </div>
                </div>
            </div>

            {/* Stats */}
            {stats.count > 0 && (
                <div className="flex gap-2 sm:gap-4 mb-3 sm:mb-4 text-xs sm:text-sm">
                    <span className="text-green-400">{stats.count} hisse bulundu</span>
                    <span className="text-gray-500">/ {stats.total_scanned} taranan</span>
                </div>
            )}

            {/* Results Table */}
            {results.length === 0 ? (
                <div className="bg-gray-900/50 border border-gray-800 rounded-lg p-8 sm:p-12 text-center">
                    <div className="text-3xl sm:text-4xl mb-3 sm:mb-4">📊</div>
                    <div className="text-gray-400 text-sm sm:text-base">Henüz analiz çalıştırılmadı</div>
                    <div className="text-gray-600 text-xs sm:text-sm mt-2">
                        Yukarıdaki butona tıklayarak analizi başlatın
                    </div>
                </div>
            ) : (
                <div className="bg-gray-900/50 border border-gray-800 rounded-lg overflow-hidden">
                    <div className="overflow-x-auto">
                        <table className="w-full min-w-[500px]">
                            <thead className="bg-gray-800/50">
                                <tr>
                                    <th className="text-left px-2 sm:px-4 py-2 sm:py-3 text-gray-400 text-xs sm:text-sm font-medium">Sembol</th>
                                    <th className="text-right px-2 sm:px-4 py-2 sm:py-3 text-gray-400 text-xs sm:text-sm font-medium">Kapanış</th>
                                    <th
                                        className="text-right px-2 sm:px-4 py-2 sm:py-3 text-gray-400 text-xs sm:text-sm font-medium cursor-pointer hover:text-white"
                                        onClick={() => handleSort('change_percent')}
                                    >
                                        Değişim <SortIcon field="change_percent" />
                                    </th>
                                    <th
                                        className="text-right px-2 sm:px-4 py-2 sm:py-3 text-gray-400 text-xs sm:text-sm font-medium cursor-pointer hover:text-white"
                                        onClick={() => handleSort('relative_volume')}
                                    >
                                        <span className="hidden sm:inline">Bağıl </span>Hacim <SortIcon field="relative_volume" />
                                    </th>
                                    <th
                                        className="text-right px-2 sm:px-4 py-2 sm:py-3 text-gray-400 text-xs sm:text-sm font-medium cursor-pointer hover:text-white hidden sm:table-cell"
                                        onClick={() => handleSort('volume')}
                                    >
                                        Lot <SortIcon field="volume" />
                                    </th>
                                    <th className="text-center px-2 sm:px-4 py-2 sm:py-3 text-gray-400 text-xs sm:text-sm font-medium">+</th>
                                </tr>
                            </thead>
                            <tbody>
                                {sortedResults.map((result, idx) => (
                                    <tr key={result.ticker} className="border-t border-gray-800 hover:bg-gray-800/30">
                                        <td className="px-2 sm:px-4 py-2 sm:py-3">
                                            <button
                                                onClick={() => openChartModal(result)}
                                                className="text-white font-mono font-bold hover:text-purple-400 transition-colors flex items-center gap-1 sm:gap-2 text-xs sm:text-sm"
                                            >
                                                {result.symbol}
                                                <span className="text-xs text-gray-500">📊</span>
                                            </button>
                                        </td>
                                        <td className="px-2 sm:px-4 py-2 sm:py-3 text-right text-white font-mono text-xs sm:text-sm">
                                            {result.close.toFixed(2)}
                                        </td>
                                        <td className="px-2 sm:px-4 py-2 sm:py-3 text-right">
                                            <span className={`font-bold text-xs sm:text-sm ${result.change_percent >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                                {result.change_percent >= 0 ? '+' : ''}{result.change_percent.toFixed(2)}%
                                            </span>
                                        </td>
                                        <td className="px-2 sm:px-4 py-2 sm:py-3 text-right">
                                            <span className={`font-mono text-xs sm:text-sm ${result.relative_volume >= 3 ? 'text-yellow-400 font-bold' : result.relative_volume >= 2 ? 'text-blue-400' : 'text-gray-400'}`}>
                                                {result.relative_volume.toFixed(1)}x
                                            </span>
                                        </td>
                                        <td className="px-2 sm:px-4 py-2 sm:py-3 text-right text-gray-300 font-mono text-xs sm:text-sm hidden sm:table-cell">
                                            {formatVolume(result.volume)}
                                        </td>
                                        <td className="px-2 sm:px-4 py-2 sm:py-3 text-center">
                                            <button
                                                onClick={() => openAddToStrategyModal(result)}
                                                className="px-2 sm:px-3 py-1 bg-blue-600/20 hover:bg-blue-600/40 text-blue-400 rounded text-xs sm:text-sm transition-colors"
                                            >
                                                +<span className="hidden sm:inline"> Ekle</span>
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
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
                            Stratejiye Ekle
                        </h3>

                        <div className="mb-4">
                            <div className="text-gray-400 mb-2">
                                <span className="font-bold text-white">{addToStrategyModal.symbol}</span>
                                {' '}hangi stratejiye eklensin?
                            </div>
                        </div>

                        <div className="space-y-2 max-h-60 overflow-y-auto mb-4">
                            {strategies.filter(s => s.is_active).length === 0 ? (
                                <div className="text-gray-500 text-center py-4">
                                    Aktif strateji bulunamadı
                                </div>
                            ) : (
                                strategies.filter(s => s.is_active).map(strategy => (
                                    <button
                                        key={strategy.id}
                                        onClick={() => addToStrategy(strategy.id)}
                                        disabled={addingToStrategy}
                                        className="w-full px-4 py-3 bg-gray-800 hover:bg-gray-700 disabled:bg-gray-800 text-left rounded-lg transition-colors flex items-center justify-between"
                                    >
                                        <div>
                                            <div className="text-white font-medium">{strategy.name}</div>
                                            <div className="text-gray-500 text-sm">{strategy.strategy_type}</div>
                                        </div>
                                        <span className="text-blue-400">→</span>
                                    </button>
                                ))
                            )}
                        </div>

                        <button
                            onClick={() => setAddToStrategyModal(null)}
                            className="w-full px-4 py-3 bg-gray-700 hover:bg-gray-600 text-white rounded transition-colors"
                        >
                            İptal
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}
