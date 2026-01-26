import { useState, useEffect, useCallback } from 'react';
import ChartModal from './ChartModal';
import { useToast } from '../contexts/ToastContext';

const API_BASE = import.meta.env.VITE_API_BASE || '';

export default function EODAnalysisPanel({ strategies }) {
    const { addToast } = useToast();
    const [results, setResults] = useState([]);
    const [loading, setLoading] = useState(false);
    const [lastRun, setLastRun] = useState(null);
    const [stats, setStats] = useState({ count: 0, total_scanned: 0 });
    const [sortBy, setSortBy] = useState('change_percent'); // change_percent, relative_volume, volume_tl
    const [sortDir, setSortDir] = useState('desc');
    const [chartModal, setChartModal] = useState(null);
    const [addToStrategyModal, setAddToStrategyModal] = useState(null);
    const [addingToStrategy, setAddingToStrategy] = useState(false);

    // Filters
    const [filters, setFilters] = useState({
        min_change: 0,
        min_relative_volume: 2,
        min_volume: 100000000,
    });

    // Load last results when component mounts
    useEffect(() => {
        const loadLastResults = async () => {
            try {
                const res = await fetch(`${API_BASE}/strategies/eod-analysis/status`);
                if (res.ok) {
                    const data = await res.json();
                    if (data.last_results && data.last_results.length > 0) {
                        setResults(data.last_results);
                        setStats({ count: data.last_results.length, total_scanned: data.last_results_count });
                        if (data.last_run_at) {
                            setLastRun(new Date(data.last_run_at));
                        }
                    }
                }
            } catch (err) {
                console.error('Failed to load last EOD results:', err);
            }
        };
        loadLastResults();
    }, []);

    const runAnalysis = useCallback(async () => {
        setLoading(true);
        setResults([]);  // Clear old results
        setStats({ count: 0, total_scanned: 0 });  // Reset stats
        try {
            const params = new URLSearchParams({
                min_change: filters.min_change,
                min_relative_volume: filters.min_relative_volume,
                min_volume: filters.min_volume,
            });

            const res = await fetch(`${API_BASE}/strategies/eod-analysis?${params}`);
            if (res.ok) {
                const data = await res.json();
                setResults(data.results);
                setStats({ count: data.count, total_scanned: data.total_scanned });
                setLastRun(new Date());
                addToast(`Analiz tamamlandı: ${data.count} hisse bulundu`, 'success');
            } else {
                addToast('Analiz başarısız', 'error');
            }
        } catch (err) {
            console.error('Failed to run EOD analysis:', err);
            addToast('Bağlantı hatası', 'error');
        } finally {
            setLoading(false);
        }
    }, [filters, addToast]);

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
            <div className="flex items-center justify-between mb-6">
                <div>
                    <h2 className="text-xl font-bold text-white">Gün Sonu Analizi</h2>
                    <p className="text-gray-500 text-sm">
                        BIST'te işlem gören hisseleri filtreleyin
                    </p>
                </div>
                <div className="flex items-center gap-4">
                    {lastRun && (
                        <span className="text-gray-500 text-sm">
                            Son: {lastRun.toLocaleTimeString('tr-TR')}
                        </span>
                    )}
                    <button
                        onClick={runAnalysis}
                        disabled={loading}
                        className="px-6 py-3 bg-purple-600 hover:bg-purple-500 disabled:bg-gray-600 text-white font-bold rounded-lg transition-colors flex items-center gap-2"
                    >
                        {loading ? (
                            <>
                                <span className="animate-spin">⏳</span>
                                Taranıyor...
                            </>
                        ) : (
                            <>
                                🔍 Analizi Çalıştır
                            </>
                        )}
                    </button>
                </div>
            </div>

            {/* Filters */}
            <div className="bg-gray-900/50 border border-gray-800 rounded-lg p-4 mb-6">
                <h3 className="text-sm font-bold text-gray-400 mb-3">Filtreler</h3>
                <div className="grid grid-cols-3 gap-4">
                    <div>
                        <label className="block text-gray-500 text-xs mb-1">Min. Değişim (%)</label>
                        <input
                            type="number"
                            step="0.1"
                            value={filters.min_change}
                            onChange={(e) => setFilters({ ...filters, min_change: parseFloat(e.target.value) || 0 })}
                            className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-white font-mono focus:border-purple-500 focus:outline-none"
                        />
                    </div>
                    <div>
                        <label className="block text-gray-500 text-xs mb-1">Min. Bağıl Hacim</label>
                        <input
                            type="number"
                            step="0.1"
                            value={filters.min_relative_volume}
                            onChange={(e) => setFilters({ ...filters, min_relative_volume: parseFloat(e.target.value) || 0 })}
                            className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-white font-mono focus:border-purple-500 focus:outline-none"
                        />
                    </div>
                    <div>
                        <label className="block text-gray-500 text-xs mb-1">Min. Hacim</label>
                        <input
                            type="number"
                            step="1000000"
                            value={filters.min_volume}
                            onChange={(e) => setFilters({ ...filters, min_volume: parseFloat(e.target.value) || 0 })}
                            className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-white font-mono focus:border-purple-500 focus:outline-none"
                        />
                        <span className="text-gray-600 text-xs">{formatVolume(filters.min_volume)}</span>
                    </div>
                </div>
            </div>

            {/* Stats */}
            {stats.count > 0 && (
                <div className="flex gap-4 mb-4 text-sm">
                    <span className="text-green-400">{stats.count} hisse bulundu</span>
                    <span className="text-gray-500">/ {stats.total_scanned} taranan</span>
                </div>
            )}

            {/* Results Table */}
            {results.length === 0 ? (
                <div className="bg-gray-900/50 border border-gray-800 rounded-lg p-12 text-center">
                    <div className="text-4xl mb-4">📊</div>
                    <div className="text-gray-400">Henüz analiz çalıştırılmadı</div>
                    <div className="text-gray-600 text-sm mt-2">
                        Yukarıdaki butona tıklayarak gün sonu analizini başlatın
                    </div>
                </div>
            ) : (
                <div className="bg-gray-900/50 border border-gray-800 rounded-lg overflow-hidden">
                    <table className="w-full">
                        <thead className="bg-gray-800/50">
                            <tr>
                                <th className="text-left px-4 py-3 text-gray-400 text-sm font-medium">Sembol</th>
                                <th className="text-right px-4 py-3 text-gray-400 text-sm font-medium">Kapanış</th>
                                <th
                                    className="text-right px-4 py-3 text-gray-400 text-sm font-medium cursor-pointer hover:text-white"
                                    onClick={() => handleSort('change_percent')}
                                >
                                    Değişim <SortIcon field="change_percent" />
                                </th>
                                <th
                                    className="text-right px-4 py-3 text-gray-400 text-sm font-medium cursor-pointer hover:text-white"
                                    onClick={() => handleSort('relative_volume')}
                                >
                                    Bağıl Hacim <SortIcon field="relative_volume" />
                                </th>
                                <th
                                    className="text-right px-4 py-3 text-gray-400 text-sm font-medium cursor-pointer hover:text-white"
                                    onClick={() => handleSort('volume')}
                                >
                                    Hacim (Lot) <SortIcon field="volume" />
                                </th>
                                <th className="text-center px-4 py-3 text-gray-400 text-sm font-medium">İşlem</th>
                            </tr>
                        </thead>
                        <tbody>
                            {sortedResults.map((result, idx) => (
                                <tr key={result.ticker} className="border-t border-gray-800 hover:bg-gray-800/30">
                                    <td className="px-4 py-3">
                                        <button
                                            onClick={() => openChartModal(result)}
                                            className="text-white font-mono font-bold hover:text-purple-400 transition-colors flex items-center gap-2"
                                        >
                                            {result.symbol}
                                            <span className="text-xs text-gray-500">📊</span>
                                        </button>
                                    </td>
                                    <td className="px-4 py-3 text-right text-white font-mono">
                                        {result.close.toFixed(2)}
                                    </td>
                                    <td className="px-4 py-3 text-right">
                                        <span className={`font-bold ${result.change_percent >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                            {result.change_percent >= 0 ? '+' : ''}{result.change_percent.toFixed(2)}%
                                        </span>
                                    </td>
                                    <td className="px-4 py-3 text-right">
                                        <span className={`font-mono ${result.relative_volume >= 3 ? 'text-yellow-400 font-bold' : result.relative_volume >= 2 ? 'text-blue-400' : 'text-gray-400'}`}>
                                            {result.relative_volume.toFixed(1)}x
                                        </span>
                                    </td>
                                    <td className="px-4 py-3 text-right text-gray-300 font-mono text-sm">
                                        {formatVolume(result.volume)}
                                    </td>
                                    <td className="px-4 py-3 text-center">
                                        <button
                                            onClick={() => openAddToStrategyModal(result)}
                                            className="px-3 py-1 bg-blue-600/20 hover:bg-blue-600/40 text-blue-400 rounded text-sm transition-colors"
                                        >
                                            + Stratejiye Ekle
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
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
                <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50">
                    <div className="bg-gray-900 border border-gray-700 rounded-lg p-6 w-full max-w-md">
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
