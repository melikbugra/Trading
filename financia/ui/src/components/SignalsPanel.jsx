import { useState, useEffect, useCallback } from 'react';
import ChartModal from './ChartModal';
import { useWebSocket } from '../contexts/WebSocketContext';

const API_BASE = import.meta.env.VITE_API_BASE || '';

export default function SignalsPanel({ strategies }) {
    const { activeSignals } = useWebSocket();
    const [signals, setSignals] = useState([]);
    const [filter, setFilter] = useState('all'); // all, pending, triggered, entered
    const [marketFilter, setMarketFilter] = useState('all'); // all, bist100, binance
    const [sortBy, setSortBy] = useState('status'); // date, ticker, status
    const [loading, setLoading] = useState(true);
    const [chartModal, setChartModal] = useState(null); // { ticker, market, strategyId }
    const [entryModal, setEntryModal] = useState(null); // { signalId, ticker, entry_price }
    const [entryPrice, setEntryPrice] = useState('');

    const openChartModal = (signal) => {
        setChartModal({
            ticker: signal.ticker,
            market: signal.market,
            strategyId: signal.strategy_id
        });
    };

    const openEntryModal = (signal) => {
        setEntryModal({
            signalId: signal.id,
            ticker: signal.ticker,
            direction: signal.direction,
            suggested_price: signal.entry_price,
            stop_loss: signal.stop_loss,
            take_profit: signal.take_profit
        });
        setEntryPrice(signal.entry_price?.toString() || '');
    };

    const confirmEntry = async () => {
        if (!entryModal || !entryPrice) return;

        try {
            const res = await fetch(`${API_BASE}/strategies/signals/${entryModal.signalId}/confirm-entry`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ actual_entry_price: parseFloat(entryPrice) })
            });
            if (res.ok) {
                setEntryModal(null);
                setEntryPrice('');
                // WebSocket will update the signals
            } else {
                const err = await res.json();
                alert(err.detail || 'Hata oluştu');
            }
        } catch (err) {
            console.error('Failed to confirm entry:', err);
            alert('Bağlantı hatası');
        }
    };

    // Initial fetch
    const fetchSignals = useCallback(async () => {
        try {
            const res = await fetch(`${API_BASE}/strategies/signals/active`);
            if (res.ok) {
                const data = await res.json();
                setSignals(data);
            }
        } catch (err) {
            console.error('Failed to fetch signals:', err);
        } finally {
            setLoading(false);
        }
    }, []);

    // Fetch only once on mount, then rely on WebSocket
    useEffect(() => {
        fetchSignals();
    }, [fetchSignals]);

    // Update signals when WebSocket sends new data
    useEffect(() => {
        if (activeSignals && activeSignals.length > 0) {
            setSignals(activeSignals);
            setLoading(false);
        }
    }, [activeSignals]);

    const cancelSignal = async (signalId) => {
        if (!confirm('Sinyali iptal etmek istediğinize emin misiniz?')) return;

        try {
            await fetch(`${API_BASE}/strategies/signals/${signalId}`, { method: 'DELETE' });
            // No need to fetchSignals - WebSocket will update
        } catch (err) {
            console.error('Failed to cancel signal:', err);
        }
    };

    const getStrategyName = (strategyId) => {
        const strategy = strategies.find(s => s.id === strategyId);
        return strategy?.name || `Strateji #${strategyId}`;
    };

    const getStatusBadge = (signal) => {
        const { status, entry_reached } = signal;

        // Special case: triggered + entry_reached = awaiting confirmation
        if (status === 'triggered' && entry_reached) {
            return (
                <span className="px-2 py-1 rounded text-xs font-bold border bg-purple-500/20 text-purple-400 border-purple-500/50 animate-pulse">
                    🔔 Giriş Bekliyor!
                </span>
            );
        }

        const badges = {
            pending: { color: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/50', text: '⏳ Bekliyor' },
            triggered: { color: 'bg-blue-500/20 text-blue-400 border-blue-500/50', text: '🎯 Tetiklendi' },
            entered: { color: 'bg-green-500/20 text-green-400 border-green-500/50', text: '✅ Pozisyonda' },
        };
        const badge = badges[status] || { color: 'bg-gray-500/20 text-gray-400', text: status };
        return (
            <span className={`px-2 py-1 rounded text-xs font-bold border ${badge.color}`}>
                {badge.text}
            </span>
        );
    };

    const getDirectionBadge = (direction) => {
        return direction === 'long'
            ? <span className="text-green-400 font-bold">📈 LONG</span>
            : <span className="text-red-400 font-bold">📉 SHORT</span>;
    };

    const filteredSignals = signals.filter(s => {
        // Status filter
        if (filter !== 'all' && s.status !== filter) return false;
        // Market filter
        if (marketFilter !== 'all' && s.market !== marketFilter) return false;
        return true;
    }).sort((a, b) => {
        // Sorting
        if (sortBy === 'ticker') {
            return a.ticker.localeCompare(b.ticker);
        } else if (sortBy === 'status') {
            // Priority: entry_reached (waiting) > triggered > entered > pending
            const statusOrder = { triggered: a.entry_reached ? 0 : 1, entered: 2, pending: 3 };
            const statusOrderB = { triggered: b.entry_reached ? 0 : 1, entered: 2, pending: 3 };
            return (statusOrder[a.status] ?? 4) - (statusOrderB[b.status] ?? 4);
        } else {
            // date - newest first
            return new Date(b.created_at) - new Date(a.created_at);
        }
    });

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <div className="text-gray-400">Yükleniyor...</div>
            </div>
        );
    }

    return (
        <div>
            {/* Filter Tabs */}
            <div className="flex flex-wrap gap-2 mb-4">
                {/* Status Filters */}
                <div className="flex gap-2">
                    {['all', 'pending', 'triggered', 'entered'].map(f => (
                        <button
                            key={f}
                            onClick={() => setFilter(f)}
                            className={`px-4 py-2 rounded text-sm font-medium transition-colors ${filter === f
                                ? 'bg-blue-600 text-white'
                                : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                                }`}
                        >
                            {f === 'all' ? 'Tümü' : f === 'pending' ? 'Bekleyen' : f === 'triggered' ? 'Tetiklenen' : 'Pozisyonda'}
                            {f !== 'all' && (
                                <span className="ml-1 text-xs">
                                    ({signals.filter(s => s.status === f).length})
                                </span>
                            )}
                        </button>
                    ))}
                </div>

                {/* Market Filters */}
                <div className="flex gap-2 ml-auto">
                    {[{ key: 'all', label: 'Tüm Marketler' }, { key: 'bist100', label: '🇹🇷 BIST' }, { key: 'binance', label: '₿ Binance' }].map(m => (
                        <button
                            key={m.key}
                            onClick={() => setMarketFilter(m.key)}
                            className={`px-3 py-2 rounded text-sm font-medium transition-colors ${marketFilter === m.key
                                ? 'bg-purple-600 text-white'
                                : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                                }`}
                        >
                            {m.label}
                            <span className="ml-1 text-xs">
                                ({signals.filter(s => m.key === 'all' || s.market === m.key).length})
                            </span>
                        </button>
                    ))}
                </div>

                {/* Sort Selector */}
                <select
                    value={sortBy}
                    onChange={(e) => setSortBy(e.target.value)}
                    className="px-3 py-2 bg-gray-800 border border-gray-700 rounded text-sm text-gray-300 focus:outline-none focus:border-gray-600"
                >
                    <option value="date">⏰ Tarih (Yeni)</option>
                    <option value="ticker">🔤 Sembol (A-Z)</option>
                    <option value="status">🚦 Durum (Öncelik)</option>
                </select>
            </div>

            {/* Signals List */}
            {filteredSignals.length === 0 ? (
                <div className="bg-gray-900/50 border border-gray-800 rounded-lg p-12 text-center">
                    <div className="text-4xl mb-4">📭</div>
                    <div className="text-gray-400">Aktif sinyal bulunamadı</div>
                    <div className="text-gray-600 text-sm mt-2">
                        Stratejiye sembol ekleyin ve taramayı başlatın
                    </div>
                </div>
            ) : (
                <div className="grid gap-4">
                    {filteredSignals.map(signal => (
                        <div
                            key={signal.id}
                            className="bg-gray-900/50 border border-gray-800 rounded-lg p-4 hover:border-gray-700 transition-colors"
                        >
                            <div className="flex items-start justify-between">
                                <div className="flex-1">
                                    {/* Header */}
                                    <div className="flex items-center gap-3 mb-3">
                                        <button
                                            onClick={() => openChartModal(signal)}
                                            className="text-xl font-bold text-white hover:text-purple-400 transition-colors flex items-center gap-2"
                                            title="Grafiği görüntüle"
                                        >
                                            {signal.ticker.replace('.IS', '').replace('TRY', '')}
                                            <span className="text-sm">📊</span>
                                        </button>
                                        <span className="text-gray-500 text-sm">{signal.market === 'bist100' ? 'BIST' : 'Binance'}</span>
                                        {getDirectionBadge(signal.direction)}
                                        {getStatusBadge(signal)}
                                    </div>

                                    {/* Price Levels */}
                                    {signal.status !== 'pending' && (
                                        <div className="grid grid-cols-4 gap-4 mb-3">
                                            <div>
                                                <div className="text-gray-500 text-xs">Giriş</div>
                                                <div className="text-blue-400 font-mono">{signal.entry_price?.toFixed(2) || '-'}</div>
                                            </div>
                                            <div>
                                                <div className="text-gray-500 text-xs">Güncel</div>
                                                <div className="text-white font-mono">{signal.current_price?.toFixed(2) || '-'}</div>
                                            </div>
                                            <div>
                                                <div className="text-gray-500 text-xs">Zarar Kes</div>
                                                <div className="text-red-400 font-mono">{signal.stop_loss?.toFixed(2) || '-'}</div>
                                            </div>
                                            <div>
                                                <div className="text-gray-500 text-xs">Kâr Al</div>
                                                <div className="text-green-400 font-mono">{signal.take_profit?.toFixed(2) || '-'}</div>
                                            </div>
                                        </div>
                                    )}

                                    {/* Meta Info */}
                                    <div className="flex items-center gap-4 text-xs text-gray-500">
                                        <span>📋 {getStrategyName(signal.strategy_id)}</span>
                                        <span>🕐 {new Date(signal.created_at).toLocaleString('tr-TR', { timeZone: 'Europe/Istanbul' })}</span>
                                        {signal.notes && <span className="text-gray-400 italic">{signal.notes}</span>}
                                    </div>
                                </div>

                                {/* Actions */}
                                <div className="flex flex-col gap-2">
                                    {/* Show "Pozisyona Gir" button if entry is reached */}
                                    {signal.status === 'triggered' && signal.entry_reached && (
                                        <button
                                            onClick={() => openEntryModal(signal)}
                                            className="px-3 py-2 bg-green-600 hover:bg-green-500 text-white rounded text-sm font-bold transition-colors animate-pulse"
                                        >
                                            ✅ Pozisyona Gir
                                        </button>
                                    )}
                                    <button
                                        onClick={() => cancelSignal(signal.id)}
                                        className="px-3 py-2 bg-red-600/20 hover:bg-red-600/40 text-red-400 rounded text-sm transition-colors"
                                    >
                                        ✕ İptal
                                    </button>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* Chart Modal */}
            {chartModal && (
                <ChartModal
                    ticker={chartModal.ticker}
                    market={chartModal.market}
                    strategyId={chartModal.strategyId}
                    onClose={() => setChartModal(null)}
                />
            )}

            {/* Entry Confirmation Modal */}
            {entryModal && (
                <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50">
                    <div className="bg-gray-900 border border-gray-700 rounded-lg p-6 w-full max-w-md">
                        <h3 className="text-xl font-bold text-white mb-4">
                            ✅ Pozisyona Giriş Onayı
                        </h3>

                        <div className="mb-4">
                            <div className="text-gray-400 mb-2">
                                <span className="font-bold text-white">{entryModal.ticker}</span>
                                {' '}için {entryModal.direction === 'long' ? '📈 LONG' : '📉 SHORT'} pozisyonu
                            </div>

                            <div className="grid grid-cols-3 gap-3 text-sm mb-4">
                                <div className="bg-gray-800 p-2 rounded text-center">
                                    <div className="text-gray-500 text-xs">Önerilen</div>
                                    <div className="text-blue-400 font-mono">{entryModal.suggested_price?.toFixed(2)}</div>
                                </div>
                                <div className="bg-gray-800 p-2 rounded text-center">
                                    <div className="text-gray-500 text-xs">Stop Loss</div>
                                    <div className="text-red-400 font-mono">{entryModal.stop_loss?.toFixed(2)}</div>
                                </div>
                                <div className="bg-gray-800 p-2 rounded text-center">
                                    <div className="text-gray-500 text-xs">Kâr Al</div>
                                    <div className="text-green-400 font-mono">{entryModal.take_profit?.toFixed(2)}</div>
                                </div>
                            </div>
                        </div>

                        <div className="mb-4">
                            <label className="block text-gray-400 text-sm mb-2">
                                Gerçek Giriş Fiyatınız:
                            </label>
                            <input
                                type="number"
                                step="0.01"
                                value={entryPrice}
                                onChange={(e) => setEntryPrice(e.target.value)}
                                className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded text-white text-lg font-mono focus:border-green-500 focus:outline-none"
                                placeholder="Örn: 123.45"
                                autoFocus
                            />
                            <div className="text-gray-500 text-xs mt-1">
                                Aracı kurumunuzdaki gerçek işlem fiyatını girin
                            </div>
                        </div>

                        <div className="flex gap-3">
                            <button
                                onClick={() => { setEntryModal(null); setEntryPrice(''); }}
                                className="flex-1 px-4 py-3 bg-gray-700 hover:bg-gray-600 text-white rounded transition-colors"
                            >
                                İptal
                            </button>
                            <button
                                onClick={confirmEntry}
                                disabled={!entryPrice}
                                className="flex-1 px-4 py-3 bg-green-600 hover:bg-green-500 disabled:bg-gray-600 disabled:cursor-not-allowed text-white font-bold rounded transition-colors"
                            >
                                ✅ Onayla
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
