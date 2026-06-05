import { useState, useEffect, useCallback } from 'react';
import ChartModal from './ChartModal';
import { useWebSocket } from '../contexts/WebSocketContext';
import { useToast } from '../contexts/ToastContext';
import { useSimulation } from '../contexts/SimulationContext';

const API_BASE = import.meta.env.VITE_API_BASE || '';

export default function SignalsPanel({ strategies }) {
    const { activeSignals } = useWebSocket();
    const { addToast } = useToast();
    const { isSimulationMode, simSignals, getApiUrl } = useSimulation();
    const [signals, setSignals] = useState([]);
    const [filter, setFilter] = useState('all'); // all, pending, triggered, entered
    const [directionFilter, setDirectionFilter] = useState('long'); // all, long, short
    const [marketFilter, setMarketFilter] = useState('all'); // all, bist100, binance
    const [strategyFilter, setStrategyFilter] = useState('all'); // all or strategy_id
    const [sortBy, setSortBy] = useState('status'); // date, ticker, status
    const [loading, setLoading] = useState(true);
    const [chartModal, setChartModal] = useState(null); // { ticker, market, strategyId }
    const [entryModal, setEntryModal] = useState(null); // { signalId, ticker, entry_price }
    const [entryPrice, setEntryPrice] = useState('');
    const [entryLots, setEntryLots] = useState('');
    const [entryStopLoss, setEntryStopLoss] = useState('');
    const [entryTakeProfit, setEntryTakeProfit] = useState('');
    const [exitModal, setExitModal] = useState(null); // { signalId, ticker, direction, remaining_lots }
    const [exitPrice, setExitPrice] = useState('');
    const [exitLots, setExitLots] = useState('');

    // Use simulation signals when in simulation mode
    const effectiveSignals = isSimulationMode ? simSignals : activeSignals;

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
        setEntryStopLoss(signal.stop_loss?.toString() || '');
        setEntryTakeProfit(signal.take_profit?.toString() || '');
    };

    const openExitModal = (signal) => {
        setExitModal({
            signalId: signal.id,
            ticker: signal.ticker,
            direction: signal.direction,
            entry_price: signal.actual_entry_price || signal.entry_price,
            current_price: signal.current_price,
            remaining_lots: signal.remaining_lots || 0
        });
        setExitPrice(signal.current_price?.toString() || '');
        setExitLots(signal.remaining_lots?.toString() || '');
    };

    const confirmEntry = async () => {
        if (!entryModal || !entryPrice || !entryLots) return;

        try {
            const payload = {
                actual_entry_price: parseFloat(entryPrice),
                lots: parseFloat(entryLots)
            };
            if (entryStopLoss) payload.stop_loss = parseFloat(entryStopLoss);
            if (entryTakeProfit) payload.take_profit = parseFloat(entryTakeProfit);

            // Use simulation endpoint when in simulation mode
            const endpoint = isSimulationMode
                ? `${API_BASE}/simulation/signals/${entryModal.signalId}/confirm-entry`
                : `${API_BASE}/strategies/signals/${entryModal.signalId}/confirm-entry`;

            const res = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (res.ok) {
                addToast(`${entryModal.ticker} pozisyona alındı: ${entryLots} lot @ ${entryPrice}`, 'success');
                setEntryModal(null);
                setEntryPrice('');
                setEntryLots('');
                setEntryStopLoss('');
                setEntryTakeProfit('');
                // WebSocket will update the signals
            } else {
                const err = await res.json();
                addToast(err.detail || 'Hata oluştu', 'error');
            }
        } catch (err) {
            console.error('Failed to confirm entry:', err);
            addToast('Bağlantı hatası', 'error');
        }
    };

    const confirmExit = async () => {
        if (!exitModal || !exitPrice || !exitLots) return;

        try {
            // Use simulation endpoint when in simulation mode
            const endpoint = isSimulationMode
                ? `${API_BASE}/simulation/signals/${exitModal.signalId}/close-position`
                : `${API_BASE}/strategies/signals/${exitModal.signalId}/close-position`;

            const res = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    exit_price: parseFloat(exitPrice),
                    lots: parseFloat(exitLots)
                })
            });
            if (res.ok) {
                const data = await res.json();
                const pnlText = `${data.profit_tl >= 0 ? '+' : ''}${data.profit_tl.toLocaleString('tr-TR')} TL`;
                const lotsText = data.is_fully_closed
                    ? `${exitLots} lot satıldı (pozisyon kapatıldı)`
                    : `${exitLots} lot satıldı (kalan: ${data.remaining_lots})`;
                addToast(
                    `${exitModal.ticker}: ${lotsText} | ${pnlText}`,
                    data.profit_tl >= 0 ? 'success' : 'warning',
                    5000
                );
                setExitModal(null);
                setExitPrice('');
                setExitLots('');
                // WebSocket will update the signals
            } else {
                const err = await res.json();
                addToast(err.detail || 'Hata oluştu', 'error');
            }
        } catch (err) {
            console.error('Failed to close position:', err);
            addToast('Bağlantı hatası', 'error');
        }
    };

    // Initial fetch
    const fetchSignals = useCallback(async () => {
        try {
            // Use simulation endpoint when in simulation mode
            const endpoint = isSimulationMode
                ? `${API_BASE}/simulation/signals/active`
                : `${API_BASE}/strategies/signals/active`;

            const res = await fetch(endpoint);
            if (res.ok) {
                const data = await res.json();
                setSignals(data);
            }
        } catch (err) {
            console.error('Failed to fetch signals:', err);
        } finally {
            setLoading(false);
        }
    }, [isSimulationMode]);

    // Fetch only once on mount, then rely on WebSocket
    useEffect(() => {
        fetchSignals();
    }, [fetchSignals]);

    // Update signals when WebSocket sends new data
    useEffect(() => {
        if (effectiveSignals && effectiveSignals.length > 0) {
            setSignals(effectiveSignals);
            setLoading(false);
        }
    }, [effectiveSignals]);

    const cancelSignal = async (signalId) => {
        if (!confirm('Sinyali iptal etmek istediğinize emin misiniz?')) return;

        try {
            // Use simulation endpoint when in simulation mode
            const endpoint = isSimulationMode
                ? `${API_BASE}/simulation/signals/${signalId}`
                : `${API_BASE}/strategies/signals/${signalId}`;

            await fetch(endpoint, { method: 'DELETE' });
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
            missed: { color: 'bg-gray-500/20 text-gray-400 border-gray-500/50', text: '⏭️ Kaçırıldı' },
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
        // Direction filter
        if (directionFilter !== 'all' && s.direction !== directionFilter) return false;
        // Market filter
        if (marketFilter !== 'all' && s.market !== marketFilter) return false;
        // Strategy filter
        if (strategyFilter !== 'all' && s.strategy_id !== parseInt(strategyFilter)) return false;
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
            <div className="flex flex-wrap items-center gap-2 mb-4">
                {/* Status Filters */}
                <div className="flex gap-1 sm:gap-2 shrink-0">
                    {['all', 'pending', 'triggered', 'entered'].map(f => (
                        <button
                            key={f}
                            onClick={() => setFilter(f)}
                            className={`px-2 sm:px-3 py-1.5 sm:py-2 rounded text-xs sm:text-sm font-medium transition-colors whitespace-nowrap ${filter === f
                                ? 'bg-blue-600 text-white'
                                : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                                }`}
                        >
                            {f === 'all' ? 'Tümü' : f === 'pending' ? 'Bekleyen' : f === 'triggered' ? 'Tetik' : 'Pozisyon'}
                            {f !== 'all' && (
                                <span className="ml-1 text-xs">
                                    ({signals.filter(s => s.status === f).length})
                                </span>
                            )}
                        </button>
                    ))}
                </div>

                {/* Separator */}
                <div className="hidden sm:block w-px h-6 bg-gray-700" />

                {/* Direction Filters */}
                <div className="flex gap-1 sm:gap-2 shrink-0">
                    {[{ key: 'all', label: 'Tümü' }, { key: 'long', label: '📈 Long' }, { key: 'short', label: '📉 Short' }].map(d => (
                        <button
                            key={d.key}
                            onClick={() => setDirectionFilter(d.key)}
                            className={`px-2 sm:px-3 py-1.5 sm:py-2 rounded text-xs sm:text-sm font-medium transition-colors whitespace-nowrap ${directionFilter === d.key
                                ? 'bg-green-600 text-white'
                                : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                                }`}
                        >
                            {d.label}
                        </button>
                    ))}
                </div>

                {/* Separator */}
                <div className="hidden sm:block w-px h-6 bg-gray-700" />

                {/* Market Filters */}
                <div className="flex gap-1 sm:gap-2 shrink-0">
                    {[{ key: 'all', label: 'Tümü', shortLabel: 'Tümü' }, { key: 'bist100', label: '🇹🇷 BIST', shortLabel: '🇹🇷' }, { key: 'us', label: '🇺🇸 ABD', shortLabel: '🇺🇸' }, { key: 'binance', label: '₿ Binance', shortLabel: '₿' }].map(m => (
                        <button
                            key={m.key}
                            onClick={() => setMarketFilter(m.key)}
                            className={`px-2 sm:px-3 py-1.5 sm:py-2 rounded text-xs sm:text-sm font-medium transition-colors whitespace-nowrap ${marketFilter === m.key
                                ? 'bg-purple-600 text-white'
                                : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                                }`}
                        >
                            <span className="sm:hidden">{m.shortLabel}</span>
                            <span className="hidden sm:inline">{m.label}</span>
                            <span className="ml-1 text-xs hidden sm:inline">
                                ({signals.filter(s => m.key === 'all' || s.market === m.key).length})
                            </span>
                        </button>
                    ))}
                </div>

                {/* Strategy Filter & Sort - pushed to right */}
                <div className="flex gap-1 sm:gap-2 ml-auto shrink-0">
                    <select
                        value={strategyFilter}
                        onChange={(e) => setStrategyFilter(e.target.value)}
                        className="px-2 sm:px-3 py-1.5 sm:py-2 bg-gray-800 border border-gray-700 rounded text-xs sm:text-sm text-gray-300 focus:outline-none focus:border-gray-600"
                    >
                        <option value="all">📋 Tüm Stratejiler</option>
                        {strategies.map(s => (
                            <option key={s.id} value={s.id}>
                                {s.name}
                            </option>
                        ))}
                    </select>

                    <select
                        value={sortBy}
                        onChange={(e) => setSortBy(e.target.value)}
                        className="px-2 sm:px-3 py-1.5 sm:py-2 bg-gray-800 border border-gray-700 rounded text-xs sm:text-sm text-gray-300 focus:outline-none focus:border-gray-600"
                    >
                        <option value="date">⏰ Tarih</option>
                        <option value="ticker">🔤 A-Z</option>
                        <option value="status">🚦 Durum</option>
                    </select>
                </div>
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
                <div className="grid gap-3 sm:gap-4">
                    {filteredSignals.map(signal => (
                        <div
                            key={signal.id}
                            className="bg-gray-900/50 border border-gray-800 rounded-lg p-3 sm:p-4 hover:border-gray-700 transition-colors"
                        >
                            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                                <div className="flex-1">
                                    {/* Header */}
                                    <div className="flex flex-wrap items-center gap-2 sm:gap-3 mb-2 sm:mb-3">
                                        <button
                                            onClick={() => openChartModal(signal)}
                                            className="text-lg sm:text-xl font-bold text-white hover:text-purple-400 transition-colors flex items-center gap-1 sm:gap-2"
                                            title="Grafiği görüntüle"
                                        >
                                            {signal.ticker.replace('.IS', '').replace('TRY', '')}
                                            <span className="text-xs sm:text-sm">📊</span>
                                        </button>
                                        <span className="text-gray-500 text-xs sm:text-sm">{signal.market === 'bist100' ? 'BIST' : signal.market === 'us' ? 'ABD' : 'Binance'}</span>
                                        {getDirectionBadge(signal.direction)}
                                        {getStatusBadge(signal)}
                                    </div>

                                    {/* Price Levels */}
                                    {signal.status !== 'pending' && (
                                        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 sm:gap-4 mb-2 sm:mb-3">
                                            <div>
                                                <div className="text-gray-500 text-xs">Giriş {signal.extra_data?.entry_zone ? '(limit)' : ''}</div>
                                                <div className="text-blue-400 font-mono text-sm sm:text-base">
                                                    {signal.extra_data?.entry_zone
                                                        ? `${signal.extra_data.entry_zone.low?.toFixed(2)}–${signal.extra_data.entry_zone.high?.toFixed(2)}`
                                                        : (signal.entry_price?.toFixed(2) || '-')}
                                                </div>
                                            </div>
                                            <div>
                                                <div className="text-gray-500 text-xs">Güncel</div>
                                                <div className="text-white font-mono text-sm sm:text-base">
                                                    {signal.current_price?.toFixed(2) || '-'}
                                                    {signal.price_updated_at && (
                                                        <span className="text-gray-600 text-xs ml-1">
                                                            ({new Date(signal.price_updated_at).toLocaleString('tr-TR', {
                                                                day: '2-digit',
                                                                month: '2-digit',
                                                                hour: '2-digit',
                                                                minute: '2-digit'
                                                            })})
                                                        </span>
                                                    )}
                                                </div>
                                            </div>
                                            <div>
                                                <div className="text-gray-500 text-xs">SL</div>
                                                <div className="text-red-400 font-mono text-sm sm:text-base">{signal.stop_loss?.toFixed(2) || '-'}</div>
                                            </div>
                                            <div>
                                                <div className="text-gray-500 text-xs">TP</div>
                                                <div className="text-green-400 font-mono text-sm sm:text-base">{signal.take_profit?.toFixed(2) || '-'}</div>
                                            </div>
                                            {signal.status === 'entered' && (
                                                <div>
                                                    <div className="text-gray-500 text-xs">Lot</div>
                                                    <div className="text-purple-400 font-mono font-bold text-sm sm:text-base">{signal.remaining_lots || 0}</div>
                                                </div>
                                            )}
                                        </div>
                                    )}

                                    {/* Partial TP / Trailing (entered positions) */}
                                    {signal.status === 'entered' && (signal.extra_data?.partial_tp || signal.extra_data?.trailing_stop_current) && (
                                        <div className="flex flex-wrap items-center gap-3 mb-2 text-xs">
                                            {signal.extra_data?.partial_tp && (
                                                <span className={signal.extra_data?.tp1_hit ? 'text-green-300 font-bold' : 'text-gray-400'}>
                                                    TP1: {signal.extra_data.partial_tp.price?.toFixed(2)} (%{Math.round((signal.extra_data.partial_tp.pct ?? 0.5) * 100)}){signal.extra_data?.tp1_hit ? ' ✓ satıldı' : ''}
                                                </span>
                                            )}
                                            {signal.extra_data?.trailing_stop_current && (
                                                <span className="text-amber-400 font-bold">
                                                    🔼 Trailing Stop: {signal.extra_data.trailing_stop_current.toFixed(2)}
                                                </span>
                                            )}
                                        </div>
                                    )}

                                    {/* Meta Info */}
                                    <div className="flex flex-wrap items-center gap-2 sm:gap-4 text-xs text-gray-500">
                                        <span>📋 {getStrategyName(signal.strategy_id)}</span>
                                        <span className="hidden sm:inline">🕐 {new Date(signal.created_at).toLocaleString('tr-TR', { timeZone: 'Europe/Istanbul' })}</span>
                                        {signal.extra_data?.data_timestamp && (
                                            <span className="hidden sm:inline" title="Kararın verildiği kapanmış mum">
                                                🕯️ Mum: {new Date(signal.extra_data.data_timestamp).toLocaleString('tr-TR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}
                                            </span>
                                        )}
                                        {signal.notes && <span className="text-gray-400 italic hidden md:inline">{signal.notes}</span>}
                                    </div>
                                </div>

                                {/* Actions */}
                                <div className="flex sm:flex-col gap-2 justify-start sm:justify-center">
                                    {/* Show "Pozisyona Al" button for triggered signals */}
                                    {signal.status === 'triggered' && (
                                        <button
                                            onClick={() => openEntryModal(signal)}
                                            className={`px-3 py-2 bg-green-600 hover:bg-green-500 text-white rounded text-xs sm:text-sm font-bold transition-colors flex-1 sm:flex-none ${signal.entry_reached ? 'animate-pulse' : ''}`}
                                        >
                                            ✅ <span className="hidden sm:inline">Pozisyona </span>Al
                                        </button>
                                    )}
                                    {/* Show "Pozisyondan Çık" button for entered signals */}
                                    {signal.status === 'entered' && (
                                        <div className="flex flex-col gap-1">
                                            {signal.extra_data?.tp1_hit && (
                                                <div className="px-2 py-1 rounded text-xs font-bold text-center bg-green-900/80 text-green-300 border border-green-500">
                                                    🎯 TP1 — %{Math.round((signal.extra_data.partial_tp?.pct ?? 0.5) * 100)} sat
                                                </div>
                                            )}
                                            {signal.sl_tp_alert && (
                                                <div className={`px-2 py-1 rounded text-xs font-bold text-center animate-pulse ${signal.sl_tp_alert === 'sl_hit'
                                                    ? 'bg-red-900/80 text-red-300 border border-red-500'
                                                    : 'bg-green-900/80 text-green-300 border border-green-500'
                                                    }`}>
                                                    {signal.sl_tp_alert === 'sl_hit' ? '⚠️ SL Değdi!' : '🎯 TP Değdi!'}
                                                </div>
                                            )}
                                            <button
                                                onClick={() => openExitModal(signal)}
                                                className={`px-3 py-2 text-white rounded text-xs sm:text-sm font-bold transition-colors flex-1 sm:flex-none ${signal.sl_tp_alert
                                                    ? 'bg-red-600 hover:bg-red-500 animate-pulse'
                                                    : 'bg-orange-600 hover:bg-orange-500'
                                                    }`}
                                            >
                                                🚪 <span className="hidden sm:inline">Pozisyondan </span>Çık
                                            </button>
                                        </div>
                                    )}
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
                <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
                    <div className="bg-gray-900 border border-gray-700 rounded-lg p-4 sm:p-6 w-full max-w-md max-h-[90vh] overflow-y-auto">
                        <h3 className="text-xl font-bold text-white mb-4">
                            ✅ Pozisyona Giriş
                        </h3>

                        <div className="mb-4">
                            <div className="text-gray-400 mb-2">
                                <span className="font-bold text-white">{entryModal.ticker}</span>
                                {' '}için {entryModal.direction === 'long' ? '📈 LONG' : '📉 SHORT'} pozisyonu
                            </div>

                            <div className="bg-gray-800 p-2 rounded text-center mb-4">
                                <div className="text-gray-500 text-xs">Önerilen Giriş</div>
                                <div className="text-blue-400 font-mono">{entryModal.suggested_price?.toFixed(2)}</div>
                            </div>
                        </div>

                        <div className="space-y-4 mb-4">
                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <label className="block text-gray-400 text-sm mb-2">
                                        Giriş Fiyatı:
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
                                </div>
                                <div>
                                    <label className="block text-purple-400 text-sm mb-2">
                                        Lot Sayısı:
                                    </label>
                                    <input
                                        type="number"
                                        step="1"
                                        min="1"
                                        value={entryLots}
                                        onChange={(e) => setEntryLots(e.target.value)}
                                        className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded text-purple-400 text-lg font-mono focus:border-purple-500 focus:outline-none"
                                        placeholder="Örn: 100"
                                    />
                                </div>
                            </div>

                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <label className="block text-red-400 text-sm mb-2">
                                        Zarar Kes (SL):
                                    </label>
                                    <input
                                        type="number"
                                        step="0.01"
                                        value={entryStopLoss}
                                        onChange={(e) => setEntryStopLoss(e.target.value)}
                                        className="w-full px-4 py-2 bg-gray-800 border border-gray-600 rounded text-red-400 font-mono focus:border-red-500 focus:outline-none"
                                        placeholder={entryModal.stop_loss?.toFixed(2)}
                                    />
                                </div>
                                <div>
                                    <label className="block text-green-400 text-sm mb-2">
                                        Kâr Al (TP):
                                    </label>
                                    <input
                                        type="number"
                                        step="0.01"
                                        value={entryTakeProfit}
                                        onChange={(e) => setEntryTakeProfit(e.target.value)}
                                        className="w-full px-4 py-2 bg-gray-800 border border-gray-600 rounded text-green-400 font-mono focus:border-green-500 focus:outline-none"
                                        placeholder={entryModal.take_profit?.toFixed(2)}
                                    />
                                </div>
                            </div>
                            <div className="text-gray-500 text-xs">
                                Boş bırakırsanız mevcut SL/TP değerleri kullanılır
                            </div>
                        </div>

                        <div className="flex gap-3">
                            <button
                                onClick={() => { setEntryModal(null); setEntryPrice(''); setEntryLots(''); setEntryStopLoss(''); setEntryTakeProfit(''); }}
                                className="flex-1 px-4 py-3 bg-gray-700 hover:bg-gray-600 text-white rounded transition-colors"
                            >
                                İptal
                            </button>
                            <button
                                onClick={confirmEntry}
                                disabled={!entryPrice || !entryLots}
                                className="flex-1 px-4 py-3 bg-green-600 hover:bg-green-500 disabled:bg-gray-600 disabled:cursor-not-allowed text-white font-bold rounded transition-colors"
                            >
                                ✅ Pozisyona Al
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Exit Position Modal */}
            {exitModal && (
                <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
                    <div className="bg-gray-900 border border-gray-700 rounded-lg p-4 sm:p-6 w-full max-w-md max-h-[90vh] overflow-y-auto">
                        <h3 className="text-xl font-bold text-white mb-4">
                            🚪 Pozisyondan Çıkış
                        </h3>

                        <div className="mb-4">
                            <div className="text-gray-400 mb-2">
                                <span className="font-bold text-white">{exitModal.ticker}</span>
                                {' '}{exitModal.direction === 'long' ? '📈 LONG' : '📉 SHORT'} pozisyonu
                            </div>

                            <div className="grid grid-cols-3 gap-3 text-sm mb-4">
                                <div className="bg-gray-800 p-2 rounded text-center">
                                    <div className="text-gray-500 text-xs">Giriş Fiyatı</div>
                                    <div className="text-blue-400 font-mono">{exitModal.entry_price?.toFixed(2)}</div>
                                </div>
                                <div className="bg-gray-800 p-2 rounded text-center">
                                    <div className="text-gray-500 text-xs">Güncel Fiyat</div>
                                    <div className="text-white font-mono">{exitModal.current_price?.toFixed(2)}</div>
                                </div>
                                <div className="bg-purple-800/50 p-2 rounded text-center">
                                    <div className="text-gray-500 text-xs">Mevcut Lot</div>
                                    <div className="text-purple-400 font-mono font-bold">{exitModal.remaining_lots}</div>
                                </div>
                            </div>
                        </div>

                        <div className="grid grid-cols-2 gap-3 mb-4">
                            <div>
                                <label className="block text-gray-400 text-sm mb-2">
                                    Çıkış Fiyatı:
                                </label>
                                <input
                                    type="number"
                                    step="0.01"
                                    value={exitPrice}
                                    onChange={(e) => setExitPrice(e.target.value)}
                                    className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded text-white text-lg font-mono focus:border-orange-500 focus:outline-none"
                                    placeholder="Örn: 125.50"
                                    autoFocus
                                />
                            </div>
                            <div>
                                <label className="block text-purple-400 text-sm mb-2">
                                    Satılacak Lot:
                                </label>
                                <input
                                    type="number"
                                    step="1"
                                    min="1"
                                    max={exitModal.remaining_lots}
                                    value={exitLots}
                                    onChange={(e) => setExitLots(e.target.value)}
                                    className="w-full px-4 py-3 bg-gray-800 border border-gray-600 rounded text-purple-400 text-lg font-mono focus:border-purple-500 focus:outline-none"
                                    placeholder={exitModal.remaining_lots?.toString()}
                                />
                            </div>
                        </div>

                        {/* Quick lot selection buttons */}
                        <div className="flex gap-2 mb-4">
                            <button
                                onClick={() => setExitLots(Math.ceil(exitModal.remaining_lots * 0.25).toString())}
                                className="flex-1 px-2 py-1 bg-gray-700 hover:bg-gray-600 text-gray-300 text-xs rounded"
                            >
                                25%
                            </button>
                            <button
                                onClick={() => setExitLots(Math.ceil(exitModal.remaining_lots * 0.5).toString())}
                                className="flex-1 px-2 py-1 bg-gray-700 hover:bg-gray-600 text-gray-300 text-xs rounded"
                            >
                                50%
                            </button>
                            <button
                                onClick={() => setExitLots(Math.ceil(exitModal.remaining_lots * 0.75).toString())}
                                className="flex-1 px-2 py-1 bg-gray-700 hover:bg-gray-600 text-gray-300 text-xs rounded"
                            >
                                75%
                            </button>
                            <button
                                onClick={() => setExitLots(exitModal.remaining_lots.toString())}
                                className="flex-1 px-2 py-1 bg-orange-700 hover:bg-orange-600 text-white text-xs rounded font-bold"
                            >
                                Tümü
                            </button>
                        </div>

                        {exitPrice && exitLots && exitModal.entry_price && (
                            <div className="mb-4 p-3 bg-gray-800 rounded">
                                <div className="text-gray-400 text-sm mb-1">Tahmini Kâr/Zarar:</div>
                                {(() => {
                                    const entry = exitModal.entry_price;
                                    const exit = parseFloat(exitPrice);
                                    const lots = parseFloat(exitLots);
                                    const pnlPercent = exitModal.direction === 'long'
                                        ? ((exit - entry) / entry) * 100
                                        : ((entry - exit) / entry) * 100;
                                    const pnlTL = exitModal.direction === 'long'
                                        ? (exit - entry) * lots
                                        : (entry - exit) * lots;
                                    return (
                                        <div className="flex items-center gap-4">
                                            <div className={`text-2xl font-bold ${pnlTL >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                                {pnlTL >= 0 ? '+' : ''}{pnlTL.toLocaleString('tr-TR', { maximumFractionDigits: 2 })} TL
                                            </div>
                                            <div className={`text-sm ${pnlPercent >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                                ({pnlPercent >= 0 ? '+' : ''}{pnlPercent.toFixed(2)}%)
                                            </div>
                                        </div>
                                    );
                                })()}
                            </div>
                        )}

                        <div className="flex gap-3">
                            <button
                                onClick={() => { setExitModal(null); setExitPrice(''); setExitLots(''); }}
                                className="flex-1 px-4 py-3 bg-gray-700 hover:bg-gray-600 text-white rounded transition-colors"
                            >
                                İptal
                            </button>
                            <button
                                onClick={confirmExit}
                                disabled={!exitPrice || !exitLots}
                                className="flex-1 px-4 py-3 bg-orange-600 hover:bg-orange-500 disabled:bg-gray-600 disabled:cursor-not-allowed text-white font-bold rounded transition-colors"
                            >
                                {parseFloat(exitLots) >= exitModal.remaining_lots ? '🚪 Pozisyonu Kapat' : '📤 Kısmi Satış'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
