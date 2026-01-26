import { useState, useEffect, useCallback } from 'react';

const API_BASE = import.meta.env.VITE_API_BASE || '';

export default function TradeHistoryPanel({ strategies }) {
    const [trades, setTrades] = useState([]);
    const [stats, setStats] = useState(null);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState({ market: '', result: '' });

    const fetchTrades = useCallback(async () => {
        try {
            let url = `${API_BASE}/strategies/trades?limit=100`;
            if (filter.market) url += `&market=${filter.market}`;
            if (filter.result) url += `&result=${filter.result}`;

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
    }, [filter]);

    const fetchStats = useCallback(async () => {
        try {
            let url = `${API_BASE}/strategies/trades/stats`;
            if (filter.market) url += `?market=${filter.market}`;

            const res = await fetch(url);
            if (res.ok) {
                const data = await res.json();
                setStats(data);
            }
        } catch (err) {
            console.error('Failed to fetch stats:', err);
        }
    }, [filter.market]);

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
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                    <div className="bg-gray-900/50 border border-gray-800 rounded-lg p-4 text-center">
                        <div className="text-2xl font-bold text-white">{stats.total_trades}</div>
                        <div className="text-gray-500 text-sm">Toplam İşlem</div>
                    </div>
                    <div className="bg-gray-900/50 border border-gray-800 rounded-lg p-4 text-center">
                        <div className={`text-2xl font-bold ${stats.win_rate >= 50 ? 'text-green-400' : 'text-red-400'}`}>
                            %{stats.win_rate}
                        </div>
                        <div className="text-gray-500 text-sm">Kazanç Oranı</div>
                    </div>
                    <div className="bg-gray-900/50 border border-gray-800 rounded-lg p-4 text-center">
                        <div className={`text-2xl font-bold ${stats.total_profit >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                            {stats.total_profit >= 0 ? '+' : ''}{stats.total_profit}%
                        </div>
                        <div className="text-gray-500 text-sm">Toplam Getiri</div>
                    </div>
                    <div className="bg-gray-900/50 border border-gray-800 rounded-lg p-4 text-center">
                        <div className="text-2xl font-bold text-blue-400">{stats.avg_rr}R</div>
                        <div className="text-gray-500 text-sm">Ortalama R:R</div>
                    </div>
                </div>
            )}

            {/* Filters */}
            <div className="flex gap-4 mb-4">
                <select
                    value={filter.market}
                    onChange={(e) => setFilter({ ...filter, market: e.target.value })}
                    className="bg-gray-800 border border-gray-700 text-white px-4 py-2 rounded text-sm"
                >
                    <option value="">Tüm Marketler</option>
                    <option value="bist100">🇹🇷 BIST100</option>
                    <option value="binance">₿ Binance</option>
                </select>
                <select
                    value={filter.result}
                    onChange={(e) => setFilter({ ...filter, result: e.target.value })}
                    className="bg-gray-800 border border-gray-700 text-white px-4 py-2 rounded text-sm"
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
                    <table className="w-full">
                        <thead className="bg-gray-800/50">
                            <tr>
                                <th className="text-left px-4 py-3 text-gray-400 text-sm font-medium">Tarih</th>
                                <th className="text-left px-4 py-3 text-gray-400 text-sm font-medium">Sembol</th>
                                <th className="text-left px-4 py-3 text-gray-400 text-sm font-medium">Yön</th>
                                <th className="text-left px-4 py-3 text-gray-400 text-sm font-medium">Giriş / Çıkış</th>
                                <th className="text-left px-4 py-3 text-gray-400 text-sm font-medium">Sonuç</th>
                                <th className="text-right px-4 py-3 text-gray-400 text-sm font-medium">Getiri</th>
                            </tr>
                        </thead>
                        <tbody>
                            {trades.map(trade => (
                                <tr key={trade.id} className="border-t border-gray-800 hover:bg-gray-800/30">
                                    <td className="px-4 py-3 text-gray-400 text-sm">
                                        {new Date(trade.closed_at).toLocaleString('tr-TR', {
                                            day: '2-digit',
                                            month: '2-digit',
                                            hour: '2-digit',
                                            minute: '2-digit',
                                            timeZone: 'Europe/Istanbul'
                                        })}
                                    </td>
                                    <td className="px-4 py-3">
                                        <div className="flex items-center gap-2">
                                            <span className="text-white font-mono font-bold">{trade.ticker.replace('.IS', '').replace('TRY', '')}</span>
                                            <span className={`text-xs ${trade.market === 'bist100' ? 'text-red-400' : 'text-yellow-400'
                                                }`}>
                                                {trade.market === 'bist100' ? '🇹🇷' : '₿'}
                                            </span>
                                        </div>
                                    </td>
                                    <td className="px-4 py-3">
                                        <span className={`font-bold ${trade.direction === 'long' ? 'text-green-400' : 'text-red-400'
                                            }`}>
                                            {trade.direction === 'long' ? '📈 LONG' : '📉 SHORT'}
                                        </span>
                                    </td>
                                    <td className="px-4 py-3 text-gray-300 font-mono text-sm">
                                        {trade.entry_price.toFixed(2)} → {trade.exit_price.toFixed(2)}
                                    </td>
                                    <td className="px-4 py-3">
                                        <span className={`px-2 py-1 rounded text-xs font-bold ${trade.result === 'win'
                                            ? 'bg-green-500/20 text-green-400'
                                            : trade.result === 'loss'
                                                ? 'bg-red-500/20 text-red-400'
                                                : 'bg-gray-500/20 text-gray-400'
                                            }`}>
                                            {trade.result === 'win' ? '🟢 Kazanç' : trade.result === 'loss' ? '🔴 Kayıp' : '⚪ Başabaş'}
                                        </span>
                                    </td>
                                    <td className="px-4 py-3 text-right">
                                        <div className={`font-bold ${trade.profit_percent >= 0 ? 'text-green-400' : 'text-red-400'
                                            }`}>
                                            {trade.profit_percent >= 0 ? '+' : ''}{trade.profit_percent}%
                                        </div>
                                        <div className="text-gray-500 text-xs">
                                            {trade.risk_reward_achieved}R
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}
