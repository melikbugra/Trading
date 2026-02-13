import React, { useEffect, useState } from 'react';
import { useSimulation } from '../contexts/SimulationContext';

const API_BASE = import.meta.env.VITE_API_BASE || '';

const BacktestResultsModal = ({ onClose, onGoToHistory }) => {
    const { backtestResults, clearBacktestResults } = useSimulation();
    const [summary, setSummary] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        // If we have WS results, use those; otherwise fetch from API
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

    return (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
            <div className="bg-gray-800 rounded-lg shadow-xl w-full max-w-2xl mx-4 max-h-[90vh] overflow-hidden flex flex-col">
                {/* Header */}
                <div className="flex items-center justify-between px-6 py-4 border-b border-gray-700">
                    <div className="flex items-center gap-3">
                        <span className="text-2xl">⚡</span>
                        <h2 className="text-xl font-semibold text-white">Backtest Sonuçları</h2>
                    </div>
                    <button
                        onClick={handleClose}
                        className="text-gray-400 hover:text-white transition"
                    >
                        ✕
                    </button>
                </div>

                {/* Content */}
                <div className="p-6 space-y-6 overflow-y-auto flex-1">
                    {/* Overall Summary Cards */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                        <div className="bg-gray-700/50 rounded-lg p-3 text-center">
                            <div className="text-2xl font-bold text-white">
                                {overall?.total_trades || 0}
                            </div>
                            <div className="text-xs text-gray-400 mt-1">Toplam İşlem</div>
                        </div>
                        <div className="bg-gray-700/50 rounded-lg p-3 text-center">
                            <div className={`text-2xl font-bold ${(overall?.win_rate || 0) >= 50 ? 'text-green-400' : 'text-red-400'}`}>
                                {overall?.win_rate?.toFixed(1) || 0}%
                            </div>
                            <div className="text-xs text-gray-400 mt-1">Kazanma Oranı</div>
                        </div>
                        <div className="bg-gray-700/50 rounded-lg p-3 text-center">
                            <div className={`text-2xl font-bold font-mono ${(overall?.total_profit || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                {(overall?.total_profit || 0) >= 0 ? '+' : ''}{(overall?.total_profit || 0).toLocaleString('tr-TR')} ₺
                            </div>
                            <div className="text-xs text-gray-400 mt-1">Toplam K/Z</div>
                        </div>
                        <div className="bg-gray-700/50 rounded-lg p-3 text-center">
                            <div className={`text-2xl font-bold font-mono ${(overall?.profit_percent || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                {(overall?.profit_percent || 0) >= 0 ? '+' : ''}{(overall?.profit_percent || 0).toFixed(1)}%
                            </div>
                            <div className="text-xs text-gray-400 mt-1">Getiri</div>
                        </div>
                    </div>

                    {/* Balance Summary */}
                    <div className="flex items-center justify-between bg-gray-700/30 rounded-lg p-3">
                        <div className="text-sm text-gray-400">
                            💰 Başlangıç: <span className="text-white font-mono">{(overall?.initial_balance || 0).toLocaleString('tr-TR')} ₺</span>
                        </div>
                        <div className="text-sm text-gray-400">
                            → Son Bakiye: <span className={`font-mono font-bold ${(overall?.current_balance || 0) >= (overall?.initial_balance || 0) ? 'text-green-400' : 'text-red-400'}`}>
                                {(overall?.current_balance || 0).toLocaleString('tr-TR')} ₺
                            </span>
                        </div>
                        <div className="text-sm text-gray-400">
                            {overall?.winning_trades || 0}W / {overall?.losing_trades || 0}L
                        </div>
                    </div>

                    {/* Per-Strategy Breakdown */}
                    {perStrategy.length > 0 && (
                        <div>
                            <h3 className="text-sm font-medium text-gray-300 mb-3">📊 Strateji Bazlı Sonuçlar</h3>
                            <div className="space-y-2">
                                {perStrategy.map((s) => (
                                    <div
                                        key={s.strategy_id}
                                        className="bg-gray-700/30 border border-gray-600/50 rounded-lg p-4"
                                    >
                                        <div className="flex items-center justify-between mb-3">
                                            <div>
                                                <span className="text-white font-medium">{s.strategy_name}</span>
                                                <span className="text-gray-500 text-xs ml-2">({s.strategy_type})</span>
                                            </div>
                                            {s.total_trades > 0 && (
                                                <span className={`text-sm font-mono font-bold ${(s.total_profit_tl || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                                    {(s.total_profit_tl || 0) >= 0 ? '+' : ''}{(s.total_profit_tl || 0).toLocaleString('tr-TR')} ₺
                                                </span>
                                            )}
                                        </div>

                                        {s.total_trades === 0 ? (
                                            <p className="text-gray-500 text-sm">İşlem yapılmadı</p>
                                        ) : (
                                            <div className="grid grid-cols-3 sm:grid-cols-5 gap-2 text-center text-xs">
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
                                                    <div className={`font-bold font-mono ${(s.avg_profit_percent || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                                        {(s.avg_profit_percent || 0) >= 0 ? '+' : ''}{(s.avg_profit_percent || 0).toFixed(2)}%
                                                    </div>
                                                    <div className="text-gray-500">Ort. K/Z</div>
                                                </div>
                                            </div>
                                        )}

                                        {/* Win rate bar */}
                                        {s.total_trades > 0 && (
                                            <div className="mt-3 h-1.5 bg-red-500/30 rounded-full overflow-hidden">
                                                <div
                                                    className="h-full bg-green-500 rounded-full transition-all"
                                                    style={{ width: `${s.win_rate || 0}%` }}
                                                />
                                            </div>
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
