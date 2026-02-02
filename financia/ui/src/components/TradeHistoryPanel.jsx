import { useState, useEffect, useCallback } from 'react';
import { useSimulation } from '../contexts/SimulationContext';

const API_BASE = import.meta.env.VITE_API_BASE || '';

export default function TradeHistoryPanel({ strategies }) {
    const { isSimulationMode } = useSimulation();
    const [trades, setTrades] = useState([]);
    const [stats, setStats] = useState(null);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState({ market: '', result: '', strategy_id: '' });

    const fetchTrades = useCallback(async () => {
        try {
            // Use simulation endpoint when in simulation mode
            const baseEndpoint = isSimulationMode
                ? `${API_BASE}/simulation/trades`
                : `${API_BASE}/strategies/trades`;

            let url = `${baseEndpoint}?limit=100`;
            if (filter.market) url += `&market=${filter.market}`;
            if (filter.result) url += `&result=${filter.result}`;
            if (filter.strategy_id) url += `&strategy_id=${filter.strategy_id}`;

            const res = await fetch(url);
            if (res.ok) {
                const data = await res.json();
                setTrades(data);
            }
        } catch (err) {
            console.error('Failed to fetch trades:', err);
        } finally {
            setLoading(false);
        }
    }, [filter, isSimulationMode]);

    const fetchStats = useCallback(async () => {
        try {
            const params = new URLSearchParams();
            if (filter.market) params.append('market', filter.market);
            if (filter.strategy_id) params.append('strategy_id', filter.strategy_id);

            // Use simulation endpoint when in simulation mode
            const baseEndpoint = isSimulationMode
                ? `${API_BASE}/simulation/trades/stats`
                : `${API_BASE}/strategies/trades/stats`;

            let url = baseEndpoint;
            if (params.toString()) url += `?${params.toString()}`;

            const res = await fetch(url);
            if (res.ok) {
                const data = await res.json();
                setStats(data);
            }
        } catch (err) {
            console.error('Failed to fetch stats:', err);
        }
    }, [filter.market, filter.strategy_id, isSimulationMode]);

    useEffect(() => {
        fetchTrades();
        fetchStats();
    }, [fetchTrades, fetchStats]);

    const getStrategyName = (strategyId) => {
        const strategy = strategies.find(s => s.id === strategyId);
        return strategy?.name || `Strateji #${strategyId}`;
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <div className="text-gray-400">Yükleniyor...</div>
            </div>
        );
    }

    return (
        <div>
            {/* Stats Cards */}
            {stats && (
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2 sm:gap-4 mb-4 sm:mb-6">
                    <div className="bg-gray-900/50 border border-gray-800 rounded-lg p-2 sm:p-4 text-center">
                        <div className="text-lg sm:text-2xl font-bold text-white">{stats.total_trades}</div>
                        <div className="text-gray-500 text-xs sm:text-sm">İşlem</div>
                    </div>
                    <div className="bg-gray-900/50 border border-gray-800 rounded-lg p-2 sm:p-4 text-center">
                        <div className={`text-lg sm:text-2xl font-bold ${stats.win_rate >= 50 ? 'text-green-400' : 'text-red-400'}`}>
                            %{stats.win_rate}
                        </div>
                        <div className="text-gray-500 text-xs sm:text-sm">Kazanç</div>
                    </div>
                    <div className="bg-gradient-to-br from-gray-900/80 to-gray-800/50 border border-green-800/50 rounded-lg p-2 sm:p-4 text-center col-span-2 sm:col-span-1">
                        <div className={`text-lg sm:text-2xl font-bold ${(stats.total_profit_tl || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                            {(stats.total_profit_tl || 0) >= 0 ? '+' : ''}{(stats.total_profit_tl || 0).toLocaleString('tr-TR')} ₺
                        </div>
                        <div className="text-gray-500 text-xs sm:text-sm">Toplam</div>
                    </div>
                    <div className="bg-gray-900/50 border border-gray-800 rounded-lg p-2 sm:p-4 text-center">
                        <div className="text-lg sm:text-2xl font-bold text-purple-400">{stats.total_lots || 0}</div>
                        <div className="text-gray-500 text-xs sm:text-sm">Lot</div>
                    </div>
                    <div className="bg-gray-900/50 border border-gray-800 rounded-lg p-2 sm:p-4 text-center">
                        <div className="text-lg sm:text-2xl font-bold text-blue-400">{stats.avg_rr}R</div>
                        <div className="text-gray-500 text-xs sm:text-sm">Ort R:R</div>
                    </div>
                </div>
            )}

            {/* Filters */}
            <div className="flex flex-wrap gap-2 sm:gap-4 mb-4">
                <select
                    value={filter.market}
                    onChange={(e) => setFilter({ ...filter, market: e.target.value })}
                    className="bg-gray-800 border border-gray-700 text-white px-2 sm:px-4 py-1.5 sm:py-2 rounded text-xs sm:text-sm flex-1 sm:flex-none min-w-0"
                >
                    <option value="">Tüm Marketler</option>
                    <option value="bist100">🇹🇷 BIST100</option>
                    <option value="binance">₿ Binance</option>
                </select>
                <select
                    value={filter.strategy_id}
                    onChange={(e) => setFilter({ ...filter, strategy_id: e.target.value })}
                    className="bg-gray-800 border border-gray-700 text-white px-2 sm:px-4 py-1.5 sm:py-2 rounded text-xs sm:text-sm flex-1 sm:flex-none min-w-0"
                >
                    <option value="">📋 Tüm Stratejiler</option>
                    {strategies.map(s => (
                        <option key={s.id} value={s.id}>
                            {s.name}
                        </option>
                    ))}
                </select>
                <select
                    value={filter.result}
                    onChange={(e) => setFilter({ ...filter, result: e.target.value })}
                    className="bg-gray-800 border border-gray-700 text-white px-2 sm:px-4 py-1.5 sm:py-2 rounded text-xs sm:text-sm flex-1 sm:flex-none min-w-0"
                >
                    <option value="">Tüm Sonuçlar</option>
                    <option value="win">🟢 Kazanç</option>
                    <option value="loss">🔴 Kayıp</option>
                    <option value="breakeven">⚪ Başabaş</option>
                </select>
            </div>

            {/* Trades List */}
            {trades.length === 0 ? (
                <div className="bg-gray-900/50 border border-gray-800 rounded-lg p-12 text-center">
                    <div className="text-4xl mb-4">📊</div>
                    <div className="text-gray-400">Henüz işlem geçmişi yok</div>
                    <div className="text-gray-600 text-sm mt-2">
                        Tamamlanan işlemler burada görünecek
                    </div>
                </div>
            ) : (
                <div className="bg-gray-900/50 border border-gray-800 rounded-lg overflow-hidden">
                    <div className="overflow-x-auto">
                        <table className="w-full min-w-[600px]">
                            <thead className="bg-gray-800/50">
                                <tr>
                                    <th className="text-left px-2 sm:px-4 py-2 sm:py-3 text-gray-400 text-xs sm:text-sm font-medium">Tarih</th>
                                    <th className="text-left px-2 sm:px-4 py-2 sm:py-3 text-gray-400 text-xs sm:text-sm font-medium">Sembol</th>
                                    <th className="text-left px-2 sm:px-4 py-2 sm:py-3 text-gray-400 text-xs sm:text-sm font-medium">Yön</th>
                                    <th className="text-left px-2 sm:px-4 py-2 sm:py-3 text-gray-400 text-xs sm:text-sm font-medium">Lot</th>
                                    <th className="text-left px-2 sm:px-4 py-2 sm:py-3 text-gray-400 text-xs sm:text-sm font-medium">Fiyat</th>
                                    <th className="text-left px-2 sm:px-4 py-2 sm:py-3 text-gray-400 text-xs sm:text-sm font-medium">Sonuç</th>
                                    <th className="text-right px-2 sm:px-4 py-2 sm:py-3 text-gray-400 text-xs sm:text-sm font-medium">Kazanç</th>
                                </tr>
                            </thead>
                            <tbody>
                                {trades.map(trade => (
                                    <tr key={trade.id} className="border-t border-gray-800 hover:bg-gray-800/30">
                                        <td className="px-2 sm:px-4 py-2 sm:py-3 text-gray-400 text-xs sm:text-sm whitespace-nowrap">
                                            {new Date(trade.closed_at).toLocaleString('tr-TR', {
                                                day: '2-digit',
                                                month: '2-digit',
                                                hour: '2-digit',
                                                minute: '2-digit',
                                                timeZone: 'Europe/Istanbul'
                                            })}
                                        </td>
                                        <td className="px-2 sm:px-4 py-2 sm:py-3">
                                            <div className="flex items-center gap-1 sm:gap-2">
                                                <span className="text-white font-mono font-bold text-xs sm:text-sm">{trade.ticker.replace('.IS', '').replace('TRY', '')}</span>
                                                <span className={`text-xs ${trade.market === 'bist100' ? 'text-red-400' : 'text-yellow-400'
                                                    }`}>
                                                    {trade.market === 'bist100' ? '🇹🇷' : '₿'}
                                                </span>
                                            </div>
                                        </td>
                                        <td className="px-2 sm:px-4 py-2 sm:py-3">
                                            <span className={`font-bold text-xs sm:text-sm ${trade.direction === 'long' ? 'text-green-400' : 'text-red-400'
                                                }`}>
                                                {trade.direction === 'long' ? '📈' : '📉'}
                                            </span>
                                        </td>
                                        <td className="px-2 sm:px-4 py-2 sm:py-3 text-purple-400 font-mono font-bold text-xs sm:text-sm">
                                            {trade.lots || '-'}
                                        </td>
                                        <td className="px-2 sm:px-4 py-2 sm:py-3 text-gray-300 font-mono text-xs sm:text-sm whitespace-nowrap">
                                            {trade.entry_price.toFixed(2)} → {trade.exit_price.toFixed(2)}
                                        </td>
                                        <td className="px-2 sm:px-4 py-2 sm:py-3">
                                            <span className={`px-1.5 sm:px-2 py-0.5 sm:py-1 rounded text-xs font-bold ${trade.result === 'win'
                                                ? 'bg-green-500/20 text-green-400'
                                                : trade.result === 'loss'
                                                    ? 'bg-red-500/20 text-red-400'
                                                    : 'bg-gray-500/20 text-gray-400'
                                                }`}>
                                                {trade.result === 'win' ? '🟢' : trade.result === 'loss' ? '🔴' : '⚪'}
                                            </span>
                                        </td>
                                        <td className="px-2 sm:px-4 py-2 sm:py-3 text-right">
                                            <div className={`font-bold text-xs sm:text-sm ${(trade.profit_tl || 0) >= 0 ? 'text-green-400' : 'text-red-400'
                                                }`}>
                                                {(trade.profit_tl || 0) >= 0 ? '+' : ''}{(trade.profit_tl || 0).toLocaleString('tr-TR')} ₺
                                            </div>
                                            <div className="text-gray-500 text-xs hidden sm:block">
                                                {trade.profit_percent >= 0 ? '+' : ''}{trade.profit_percent}%
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}
        </div>
    );
}
