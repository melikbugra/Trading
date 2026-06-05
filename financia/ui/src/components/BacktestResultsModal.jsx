import React, { useEffect, useState } from 'react';
import { useSimulation } from '../contexts/SimulationContext';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const BacktestResultsModal = ({ onClose, onGoToHistory }) => {
    const { backtestResults, clearBacktestResults } = useSimulation();
    const [summary, setSummary] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (backtestResults) {
            setSummary(backtestResults);
            setLoading(false);
        } else {
            fetchSummary();
        }
    }, [backtestResults]);

    const fetchSummary = async () => {
        try {
            const res = await fetch(`${API_BASE}/simulation/backtest/summary`);
            if (res.ok) {
                const data = await res.json();
                setSummary(data);
            }
        } catch (err) {
            console.error('Failed to fetch backtest summary:', err);
        } finally {
            setLoading(false);
        }
    };

    const handleClose = () => {
        clearBacktestResults();
        onClose?.();
    };

    const handleGoToHistory = () => {
        clearBacktestResults();
        onGoToHistory?.();
    };

    if (loading) {
        return (
            <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
                <div className="bg-gray-800 rounded-lg p-8 text-center">
                    <span className="animate-spin text-3xl">⏳</span>
                    <p className="text-gray-400 mt-3">Sonuçlar yükleniyor...</p>
                </div>
            </div>
        );
    }

    if (!summary) return null;

    const overall = summary.summary || summary.overall;
    const perStrategy = summary.per_strategy || [];
    const ranked = summary.ranked_strategies || [];
    const cur = overall?.currency || '₺';
    const hasCommission = (overall?.total_commission || 0) > 0;

    const getEVColor = (ev) => {
        if (ev > 0.5) return 'text-green-400';
        if (ev > 0) return 'text-yellow-400';
        return 'text-red-400';
    };

    const getRColor = (r) => {
        if (r > 0.3) return 'text-green-400';
        if (r > 0) return 'text-yellow-400';
        return 'text-red-400';
    };

    const getRRBarWidth = (value, max) => {
        return Math.min((value / Math.max(max, 1)) * 100, 100);
    };

    return (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
            <div className="bg-gray-800 rounded-lg shadow-xl w-full max-w-3xl mx-4 max-h-[90vh] overflow-hidden flex flex-col">
                {/* Header */}
                <div className="flex items-center justify-between px-6 py-4 border-b border-gray-700">
                    <div className="flex items-center gap-3">
                        <span className="text-2xl">📊</span>
                        <h2 className="text-xl font-semibold text-white">Backtest Analizi</h2>
                    </div>
                    <button onClick={handleClose} className="text-gray-400 hover:text-white transition">✕</button>
                </div>

                {/* Content */}
                <div className="p-6 space-y-6 overflow-y-auto flex-1">
                    {/* Overall Summary — R-based */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                        <div className="bg-gray-700/50 rounded-lg p-3 text-center">
                            <div className="text-2xl font-bold text-white">{overall?.total_trades || 0}</div>
                            <div className="text-xs text-gray-400 mt-1">Toplam İşlem</div>
                        </div>
                        <div className="bg-gray-700/50 rounded-lg p-3 text-center">
                            <div className={`text-2xl font-bold ${(overall?.win_rate || 0) >= 50 ? 'text-green-400' : 'text-red-400'}`}>
                                {overall?.win_rate?.toFixed(1) || 0}%
                            </div>
                            <div className="text-xs text-gray-400 mt-1">Kazanma Oranı</div>
                        </div>
                        <div className="bg-gray-700/50 rounded-lg p-3 text-center">
                            <div className={`text-2xl font-bold font-mono ${(overall?.total_r || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                {(overall?.total_r || 0) >= 0 ? '+' : ''}{(overall?.total_r || 0).toFixed(1)}R
                            </div>
                            <div className="text-xs text-gray-400 mt-1">Toplam R</div>
                        </div>
                        <div className="bg-gray-700/50 rounded-lg p-3 text-center">
                            <div className={`text-2xl font-bold font-mono ${(overall?.avg_r_per_trade || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                {(overall?.avg_r_per_trade || 0) >= 0 ? '+' : ''}{(overall?.avg_r_per_trade || 0).toFixed(3)}R
                            </div>
                            <div className="text-xs text-gray-400 mt-1">İşlem Başına R</div>
                        </div>
                    </div>

                    {/* Money: gross / slippage / (commission) / net / max drawdown */}
                    <div className={`grid grid-cols-2 ${hasCommission ? 'sm:grid-cols-5' : 'sm:grid-cols-4'} gap-3`}>
                        <div className="bg-gray-700/50 rounded-lg p-3 text-center">
                            <div className={`text-lg font-bold font-mono ${(overall?.total_profit || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                {(overall?.total_profit || 0) >= 0 ? '+' : ''}{(overall?.total_profit || 0).toLocaleString('tr-TR')} {cur}
                            </div>
                            <div className="text-xs text-gray-400 mt-1">Brüt K/Z ({(overall?.profit_percent || 0) >= 0 ? '+' : ''}{(overall?.profit_percent || 0).toFixed(1)}%)</div>
                        </div>
                        <div className="bg-gray-700/50 rounded-lg p-3 text-center">
                            <div className="text-lg font-bold font-mono text-orange-400">
                                -{(overall?.total_slippage || 0).toLocaleString('tr-TR')} {cur}
                            </div>
                            <div className="text-xs text-gray-400 mt-1">Slippage</div>
                        </div>
                        {hasCommission && (
                            <div className="bg-gray-700/50 rounded-lg p-3 text-center">
                                <div className="text-lg font-bold font-mono text-orange-400">
                                    -{(overall?.total_commission || 0).toLocaleString('tr-TR')} {cur}
                                </div>
                                <div className="text-xs text-gray-400 mt-1">Komisyon ($1.5/işlem)</div>
                            </div>
                        )}
                        <div className="bg-gray-700/50 rounded-lg p-3 text-center">
                            <div className={`text-lg font-bold font-mono ${(overall?.net_profit || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                {(overall?.net_profit || 0) >= 0 ? '+' : ''}{(overall?.net_profit || 0).toLocaleString('tr-TR')} {cur}
                            </div>
                            <div className="text-xs text-gray-400 mt-1">Net K/Z ({(overall?.net_profit_percent || 0) >= 0 ? '+' : ''}{(overall?.net_profit_percent || 0).toFixed(1)}%)</div>
                        </div>
                        <div className="bg-gray-700/50 rounded-lg p-3 text-center">
                            <div className="text-lg font-bold font-mono text-red-400">
                                -{(overall?.max_drawdown || 0).toFixed(1)}%
                            </div>
                            <div className="text-xs text-gray-400 mt-1">Max Drawdown</div>
                        </div>
                    </div>

                    {/* W/L Count */}
                    <div className="flex items-center justify-center bg-gray-700/30 rounded-lg p-2">
                        <div className="text-sm text-gray-400">
                            <span className="text-green-400 font-bold">{overall?.winning_trades || 0}</span>
                            <span className="text-gray-500"> W</span>
                            <span className="text-gray-600 mx-2">/</span>
                            <span className="text-red-400 font-bold">{overall?.losing_trades || 0}</span>
                            <span className="text-gray-500"> L</span>
                        </div>
                    </div>

                    {/* Strategy Ranking Table */}
                    {ranked.length > 0 && (
                        <div>
                            <h3 className="text-sm font-medium text-gray-300 mb-3">🏆 Strateji Sıralaması (Beklenen Değere Göre)</h3>
                            <div className="bg-gray-700/30 rounded-lg overflow-hidden">
                                <table className="w-full text-sm">
                                    <thead>
                                        <tr className="text-gray-400 border-b border-gray-600">
                                            <th className="text-left py-2 px-3">#</th>
                                            <th className="text-left py-2 px-3">Strateji</th>
                                            <th className="text-right py-2 px-3">EV</th>
                                            <th className="text-right py-2 px-3">Toplam R</th>
                                            <th className="text-right py-2 px-3">Ort. R</th>
                                            <th className="text-right py-2 px-3">PF</th>
                                            <th className="text-center py-2 px-3">R:R</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {ranked.map((s) => (
                                            <tr key={s.rank} className="border-b border-gray-700/50 hover:bg-gray-700/30">
                                                <td className="py-2 px-3">
                                                    <span className={`font-bold ${s.rank === 1 ? 'text-yellow-400' : s.rank === 2 ? 'text-gray-300' : s.rank === 3 ? 'text-orange-400' : 'text-gray-500'}`}>
                                                        {s.rank === 1 ? '🥇' : s.rank === 2 ? '🥈' : s.rank === 3 ? '🥉' : `${s.rank}.`}
                                                    </span>
                                                </td>
                                                <td className="py-2 px-3 text-white font-medium">{s.strategy_name}</td>
                                                <td className={`py-2 px-3 text-right font-mono font-bold ${getEVColor(s.expected_value)}`}>
                                                    {s.expected_value >= 0 ? '+' : ''}{s.expected_value.toFixed(3)}%
                                                </td>
                                                <td className={`py-2 px-3 text-right font-mono font-bold ${getRColor(s.total_r)}`}>
                                                    {(s.total_r || 0) >= 0 ? '+' : ''}{(s.total_r || 0).toFixed(1)}R
                                                </td>
                                                <td className={`py-2 px-3 text-right font-mono ${getRColor(s.avg_r_per_trade)}`}>
                                                    {(s.avg_r_per_trade || 0) >= 0 ? '+' : ''}{(s.avg_r_per_trade || 0).toFixed(3)}R
                                                </td>
                                                <td className={`py-2 px-3 text-right font-mono ${s.profit_factor >= 1.5 ? 'text-green-400' : s.profit_factor >= 1 ? 'text-yellow-400' : 'text-red-400'}`}>
                                                    {s.profit_factor >= 999 ? '∞' : s.profit_factor.toFixed(2)}
                                                </td>
                                                <td className="py-2 px-3 text-center text-xs">{s.rr_verdict}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    )}

                    {/* Per-Strategy Detailed Breakdown */}
                    {perStrategy.length > 0 && (
                        <div>
                            <h3 className="text-sm font-medium text-gray-300 mb-3">📈 Detaylı Strateji Analizi</h3>
                            <div className="space-y-4">
                                {perStrategy.map((s) => (
                                    <div
                                        key={s.strategy_id}
                                        className="bg-gray-700/30 border border-gray-600/50 rounded-lg p-4"
                                    >
                                        {/* Strategy header */}
                                        <div className="flex items-center justify-between mb-3">
                                            <div className="flex items-center gap-2">
                                                {s.rank && (
                                                    <span className="text-sm">
                                                        {s.rank === 1 ? '🥇' : s.rank === 2 ? '🥈' : s.rank === 3 ? '🥉' : `#${s.rank}`}
                                                    </span>
                                                )}
                                                <span className="text-white font-medium">{s.strategy_name}</span>
                                                <span className="text-gray-500 text-xs">({s.strategy_type})</span>
                                            </div>
                                            {s.total_trades > 0 && (
                                                <span className={`text-sm font-mono font-bold ${(s.total_r || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                                    {(s.total_r || 0) >= 0 ? '+' : ''}{(s.total_r || 0).toFixed(1)}R
                                                </span>
                                            )}
                                        </div>

                                        {s.total_trades === 0 ? (
                                            <p className="text-gray-500 text-sm">İşlem yapılmadı</p>
                                        ) : (
                                            <>
                                                {/* Basic stats row */}
                                                <div className="grid grid-cols-5 gap-2 text-center text-xs mb-4">
                                                    <div>
                                                        <div className="text-white font-bold">{s.total_trades}</div>
                                                        <div className="text-gray-500">İşlem</div>
                                                    </div>
                                                    <div>
                                                        <div className={`font-bold ${s.win_rate >= 50 ? 'text-green-400' : 'text-red-400'}`}>
                                                            {s.win_rate?.toFixed(1)}%
                                                        </div>
                                                        <div className="text-gray-500">Kazanma</div>
                                                    </div>
                                                    <div>
                                                        <div className="text-green-400 font-bold">{s.winning_trades}</div>
                                                        <div className="text-gray-500">Kazanç</div>
                                                    </div>
                                                    <div>
                                                        <div className="text-red-400 font-bold">{s.losing_trades}</div>
                                                        <div className="text-gray-500">Kayıp</div>
                                                    </div>
                                                    <div>
                                                        <div className={`font-bold font-mono ${(s.avg_r_per_trade || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                                            {(s.avg_r_per_trade || 0) >= 0 ? '+' : ''}{(s.avg_r_per_trade || 0).toFixed(3)}R
                                                        </div>
                                                        <div className="text-gray-500">Ort. R</div>
                                                    </div>
                                                </div>

                                                {/* Win rate bar */}
                                                <div className="h-1.5 bg-red-500/30 rounded-full overflow-hidden mb-4">
                                                    <div
                                                        className="h-full bg-green-500 rounded-full transition-all"
                                                        style={{ width: `${s.win_rate || 0}%` }}
                                                    />
                                                </div>

                                                {/* Scientific Stats */}
                                                <div className="bg-gray-800/50 rounded-lg p-3 space-y-3">
                                                    <div className="text-xs text-gray-400 font-medium uppercase tracking-wider mb-2">📐 İstatistiksel Analiz</div>

                                                    {/* Stats grid */}
                                                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                                                        <div className="bg-gray-700/40 rounded p-2">
                                                            <div className={`font-bold font-mono text-sm ${getEVColor(s.expected_value)}`}>
                                                                {s.expected_value >= 0 ? '+' : ''}{s.expected_value.toFixed(3)}%
                                                            </div>
                                                            <div className="text-gray-500 mt-0.5">Beklenen Değer</div>
                                                        </div>
                                                        <div className="bg-gray-700/40 rounded p-2">
                                                            <div className={`font-bold font-mono text-sm ${s.profit_factor >= 1.5 ? 'text-green-400' : s.profit_factor >= 1 ? 'text-yellow-400' : 'text-red-400'}`}>
                                                                {s.profit_factor >= 999 ? '∞' : s.profit_factor.toFixed(2)}
                                                            </div>
                                                            <div className="text-gray-500 mt-0.5">Profit Factor</div>
                                                        </div>
                                                        <div className="bg-gray-700/40 rounded p-2">
                                                            <div className="font-bold font-mono text-sm text-blue-400">
                                                                %{s.kelly_percent?.toFixed(1) || 0}
                                                            </div>
                                                            <div className="text-gray-500 mt-0.5">Kelly Kriteri</div>
                                                        </div>
                                                        <div className="bg-gray-700/40 rounded p-2">
                                                            <div className="font-bold font-mono text-sm text-red-400">
                                                                -{s.max_drawdown_percent?.toFixed(2) || 0}%
                                                            </div>
                                                            <div className="text-gray-500 mt-0.5">Max Drawdown</div>
                                                        </div>
                                                    </div>

                                                    {/* R-multiple details */}
                                                    <div className="grid grid-cols-2 gap-3 text-xs">
                                                        <div className="flex justify-between items-center bg-green-500/10 rounded px-2 py-1.5">
                                                            <span className="text-gray-400">En İyi İşlem:</span>
                                                            <span className="text-green-400 font-mono font-bold">+{(s.best_r || 0).toFixed(2)}R</span>
                                                        </div>
                                                        <div className="flex justify-between items-center bg-red-500/10 rounded px-2 py-1.5">
                                                            <span className="text-gray-400">En Kötü İşlem:</span>
                                                            <span className="text-red-400 font-mono font-bold">{(s.worst_r || 0).toFixed(2)}R</span>
                                                        </div>
                                                    </div>

                                                    {/* Win/Loss averages */}
                                                    <div className="grid grid-cols-2 gap-3 text-xs">
                                                        <div className="flex justify-between items-center bg-green-500/10 rounded px-2 py-1.5">
                                                            <span className="text-gray-400">Ort. Kazanç:</span>
                                                            <span className="text-green-400 font-mono font-bold">+{(s.avg_win_percent || 0).toFixed(2)}%</span>
                                                        </div>
                                                        <div className="flex justify-between items-center bg-red-500/10 rounded px-2 py-1.5">
                                                            <span className="text-gray-400">Ort. Kayıp:</span>
                                                            <span className="text-red-400 font-mono font-bold">{(s.avg_loss_percent || 0).toFixed(2)}%</span>
                                                        </div>
                                                    </div>

                                                    {/* R:R Analysis */}
                                                    <div className="border-t border-gray-700/50 pt-3">
                                                        <div className="flex items-center justify-between mb-2">
                                                            <span className="text-xs text-gray-400 font-medium">⚖️ Risk/Ödül Analizi</span>
                                                            <span className="text-xs px-2 py-0.5 rounded border" style={{
                                                                ...(s.rr_verdict?.includes('✅') ? { borderColor: 'rgb(34, 197, 94)', color: 'rgb(74, 222, 128)', backgroundColor: 'rgba(34, 197, 94, 0.1)' } :
                                                                    s.rr_verdict?.includes('⚠️') ? { borderColor: 'rgb(234, 179, 8)', color: 'rgb(250, 204, 21)', backgroundColor: 'rgba(234, 179, 8, 0.1)' } :
                                                                        s.rr_verdict?.includes('❌') ? { borderColor: 'rgb(239, 68, 68)', color: 'rgb(248, 113, 113)', backgroundColor: 'rgba(239, 68, 68, 0.1)' } :
                                                                            { borderColor: 'rgb(107, 114, 128)', color: 'rgb(156, 163, 175)', backgroundColor: 'rgba(107, 114, 128, 0.1)' })
                                                            }}>
                                                                {s.rr_verdict}
                                                            </span>
                                                        </div>

                                                        {/* R:R visual bars */}
                                                        {(() => {
                                                            const maxRR = Math.max(s.current_rr || 0, s.optimal_rr || 0, s.breakeven_rr || 0, 3);
                                                            return (
                                                                <div className="space-y-1.5">
                                                                    <div className="flex items-center gap-2">
                                                                        <span className="text-xs text-gray-400 w-20 shrink-0">Mevcut</span>
                                                                        <div className="flex-1 bg-gray-700/50 rounded-full h-3 relative overflow-hidden">
                                                                            <div className="h-full bg-blue-500 rounded-full transition-all" style={{ width: `${getRRBarWidth(s.current_rr, maxRR)}%` }} />
                                                                        </div>
                                                                        <span className="text-xs text-blue-400 font-mono w-10 text-right">{(s.current_rr || 0).toFixed(1)}</span>
                                                                    </div>
                                                                    <div className="flex items-center gap-2">
                                                                        <span className="text-xs text-gray-400 w-20 shrink-0">Başabaş</span>
                                                                        <div className="flex-1 bg-gray-700/50 rounded-full h-3 relative overflow-hidden">
                                                                            <div className="h-full bg-yellow-500/70 rounded-full transition-all" style={{ width: `${getRRBarWidth(s.breakeven_rr >= 999 ? maxRR : s.breakeven_rr, maxRR)}%` }} />
                                                                        </div>
                                                                        <span className="text-xs text-yellow-400 font-mono w-10 text-right">{s.breakeven_rr >= 999 ? '∞' : (s.breakeven_rr || 0).toFixed(1)}</span>
                                                                    </div>
                                                                    <div className="flex items-center gap-2">
                                                                        <span className="text-xs text-gray-400 w-20 shrink-0">Optimal</span>
                                                                        <div className="flex-1 bg-gray-700/50 rounded-full h-3 relative overflow-hidden">
                                                                            <div className="h-full bg-green-500/70 rounded-full transition-all" style={{ width: `${getRRBarWidth(s.optimal_rr >= 999 ? maxRR : s.optimal_rr, maxRR)}%` }} />
                                                                        </div>
                                                                        <span className="text-xs text-green-400 font-mono w-10 text-right">{s.optimal_rr >= 999 ? '∞' : (s.optimal_rr || 0).toFixed(1)}</span>
                                                                    </div>
                                                                </div>
                                                            );
                                                        })()}
                                                    </div>

                                                    {/* Sharpe ratio */}
                                                    {s.sharpe_like_ratio !== 0 && (
                                                        <div className="flex items-center justify-between text-xs pt-1 border-t border-gray-700/30">
                                                            <span className="text-gray-500">Sharpe Benzeri Oran:</span>
                                                            <span className={`font-mono font-bold ${s.sharpe_like_ratio > 0.5 ? 'text-green-400' : s.sharpe_like_ratio > 0 ? 'text-yellow-400' : 'text-red-400'}`}>
                                                                {s.sharpe_like_ratio?.toFixed(2)}
                                                            </span>
                                                        </div>
                                                    )}
                                                </div>
                                            </>
                                        )}
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>

                {/* Footer */}
                <div className="flex gap-3 px-6 py-4 border-t border-gray-700">
                    <button
                        onClick={handleClose}
                        className="flex-1 px-4 py-2 bg-gray-700 text-gray-300 rounded-lg hover:bg-gray-600 transition"
                    >
                        Kapat
                    </button>
                    <button
                        onClick={handleGoToHistory}
                        className="flex-1 px-4 py-2 bg-yellow-600 text-white rounded-lg hover:bg-yellow-500 transition flex items-center justify-center gap-2"
                    >
                        📊 Detaylı Geçmişe Git
                    </button>
                </div>
            </div>
        </div>
    );
};

export default BacktestResultsModal;
