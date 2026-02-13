import React from 'react';
import { useSimulation } from '../contexts/SimulationContext';

const SimulationBanner = () => {
    const {
        isSimulationMode,
        simStatus,
        nextHour,
        nextDay,
        stopSimulation,
        stopBacktest,
        backtestProgress,
        backtestResults,
        reopenBacktestResults,
        isLoading,
        formatSimTime,
    } = useSimulation();

    if (!isSimulationMode) return null;

    const isBacktest = simStatus.is_backtest;
    const currentTime = simStatus.current_time ? new Date(simStatus.current_time) : null;
    const dayName = currentTime?.toLocaleDateString('tr-TR', { weekday: 'long' });
    const dateStr = currentTime?.toLocaleDateString('tr-TR', { day: '2-digit', month: '2-digit', year: 'numeric' });
    const timeStr = currentTime?.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' });

    // Backtest progress bar
    const progressPercent = backtestProgress
        ? Math.round((backtestProgress.current_day / backtestProgress.total_days) * 100)
        : 0;

    return (
        <div className={`w-full ${isBacktest
            ? 'bg-gradient-to-r from-yellow-600/90 to-orange-700/90'
            : simStatus.day_completed
                ? 'bg-gradient-to-r from-green-600/90 to-green-700/90'
                : simStatus.hour_completed
                    ? 'bg-gradient-to-r from-blue-600/90 to-blue-700/90'
                    : simStatus.is_scanning
                        ? 'bg-gradient-to-r from-orange-600/90 to-orange-700/90'
                        : 'bg-gradient-to-r from-purple-600/90 to-purple-700/90'
            }`}>
            {/* Inner container aligned with tabs */}
            <div className="max-w-6xl mx-auto px-2 sm:px-8 py-2 flex items-center justify-between gap-4">
                {/* Left: Status Info */}
                <div className="flex items-center gap-4 flex-1 min-w-0">
                    {/* Label */}
                    <div className="flex items-center gap-2 shrink-0">
                        <span className="text-xl">{isBacktest ? '⚡' : '🧪'}</span>
                        <span className="font-semibold text-white">{isBacktest ? 'BACKTEST' : 'SİMÜLASYON'}</span>
                    </div>

                    <div className="h-6 w-px bg-white/30 shrink-0" />

                    {isBacktest && backtestProgress ? (
                        /* Backtest Progress */
                        <>
                            <div className="flex items-center gap-3 flex-1 min-w-0">
                                {/* Progress bar */}
                                <div className="flex-1 min-w-[120px] max-w-[300px]">
                                    <div className="flex items-center justify-between text-xs text-white/80 mb-1">
                                        <span>{backtestProgress.current_day}/{backtestProgress.total_days} gün</span>
                                        <span>{progressPercent}%</span>
                                    </div>
                                    <div className="h-2 bg-black/30 rounded-full overflow-hidden">
                                        <div
                                            className="h-full bg-white/80 rounded-full transition-all duration-300"
                                            style={{ width: `${progressPercent}%` }}
                                        />
                                    </div>
                                </div>

                                <div className="h-6 w-px bg-white/30 shrink-0" />

                                {/* Current date */}
                                <span className="text-white/90 text-sm font-mono shrink-0">
                                    📅 {backtestProgress.current_date}
                                </span>

                                <div className="h-6 w-px bg-white/30 shrink-0" />

                                {/* Live stats */}
                                <div className="flex items-center gap-2 text-white/90 text-sm shrink-0">
                                    <span>📈 {backtestProgress.trades_so_far} işlem</span>
                                    <span className={`font-mono ${backtestProgress.total_profit >= 0 ? 'text-green-300' : 'text-red-300'}`}>
                                        {backtestProgress.total_profit >= 0 ? '+' : ''}{backtestProgress.total_profit?.toLocaleString('tr-TR')} ₺
                                    </span>
                                </div>
                            </div>
                        </>
                    ) : isBacktest ? (
                        /* Backtest completed, running (no progress yet), or starting */
                        <div className="flex items-center gap-3">
                            <span className="text-white/80 text-sm flex items-center gap-2">
                                {simStatus.is_backtest_running ? (
                                    <><span className="animate-spin">⏳</span> Backtest çalışıyor...</>
                                ) : simStatus.is_active ? (
                                    <><span>✅</span> Backtest tamamlandı</>
                                ) : (
                                    <><span className="animate-spin">⏳</span> Başlatılıyor...</>
                                )}
                            </span>
                            {!simStatus.is_backtest_running && simStatus.is_active && !backtestResults && (
                                <button
                                    onClick={reopenBacktestResults}
                                    className="px-3 py-1 bg-white/20 hover:bg-white/30 text-white text-sm rounded-lg transition flex items-center gap-1.5 font-medium"
                                >
                                    📊 Sonuçları Göster
                                </button>
                            )}
                        </div>
                    ) : (
                        /* Normal simulation info */
                        <>
                            {/* Date & Time */}
                            <div className="flex items-center gap-2 text-white/90">
                                <span className="text-lg">📅</span>
                                <span className="font-medium">{dateStr}</span>
                                <span className="text-white/60">{dayName}</span>
                            </div>

                            {currentTime && (
                                <>
                                    <div className="h-6 w-px bg-white/30" />
                                    <div className="flex items-center gap-2 text-white/90">
                                        <span className="text-lg">🕐</span>
                                        <span className="font-mono font-medium">{timeStr}</span>
                                    </div>
                                </>
                            )}

                            <div className="h-6 w-px bg-white/30" />

                            {/* Balance */}
                            <div className="flex items-center gap-3 text-white/90">
                                <div className="flex items-center gap-1">
                                    <span className="text-lg">💰</span>
                                    <span className="font-mono font-medium">
                                        {(simStatus.current_balance || 0).toLocaleString('tr-TR')} ₺
                                    </span>
                                </div>
                                {simStatus.total_profit !== 0 && (
                                    <span className={`font-mono text-sm ${simStatus.total_profit >= 0 ? 'text-green-300' : 'text-red-300'}`}>
                                        ({simStatus.total_profit >= 0 ? '+' : ''}{simStatus.total_profit?.toLocaleString('tr-TR')} ₺ / {simStatus.profit_percent >= 0 ? '+' : ''}{simStatus.profit_percent?.toFixed(1)}%)
                                    </span>
                                )}
                                {simStatus.total_trades > 0 && (
                                    <span className="text-xs text-white/70">
                                        {simStatus.winning_trades}W/{simStatus.losing_trades}L ({simStatus.win_rate?.toFixed(0)}%)
                                    </span>
                                )}
                            </div>

                            {/* Status Badge */}
                            {simStatus.is_eod_running && (
                                <>
                                    <div className="h-6 w-px bg-white/30" />
                                    <span className="px-2 py-1 bg-blue-500/30 rounded text-blue-200 text-sm font-medium flex items-center gap-1">
                                        <span className="animate-spin">📊</span> Gün Sonu Analizi...
                                    </span>
                                </>
                            )}
                            {simStatus.day_completed && !simStatus.is_eod_running && (
                                <>
                                    <div className="h-6 w-px bg-white/30" />
                                    <span className="px-2 py-1 bg-green-500/30 rounded text-green-200 text-sm font-medium">
                                        ✅ Gün Tamamlandı
                                    </span>
                                </>
                            )}
                            {simStatus.is_scanning && !simStatus.is_eod_running && (
                                <>
                                    <div className="h-6 w-px bg-white/30" />
                                    <span className="px-2 py-1 bg-orange-500/30 rounded text-orange-200 text-sm font-medium flex items-center gap-1">
                                        <span className="animate-spin">🔄</span> Taranıyor...
                                    </span>
                                </>
                            )}
                            {simStatus.hour_completed && !simStatus.day_completed && !simStatus.is_eod_running && !simStatus.is_scanning && (
                                <>
                                    <div className="h-6 w-px bg-white/30" />
                                    <span className="px-2 py-1 bg-blue-500/30 rounded text-blue-200 text-sm font-medium">
                                        ✅ Tarama Tamamlandı
                                    </span>
                                </>
                            )}
                        </>
                    )}
                </div>

                {/* Right: Controls */}
                <div className="flex items-center gap-2 shrink-0">
                    {isBacktest ? (
                        /* Backtest: only stop button */
                        <button
                            onClick={stopBacktest}
                            disabled={isLoading}
                            className="px-4 py-1.5 bg-red-500/50 hover:bg-red-500/70 text-white rounded-lg transition disabled:opacity-50 flex items-center gap-2 font-medium"
                        >
                            ⏹️ Durdur
                        </button>
                    ) : (
                        /* Normal simulation controls */
                        <>
                            {simStatus.hour_completed && !simStatus.day_completed && !simStatus.is_eod_running && (
                                <button
                                    onClick={nextHour}
                                    disabled={isLoading || simStatus.is_scanning}
                                    className="px-4 py-1.5 bg-blue-500/50 hover:bg-blue-500/70 text-white rounded-lg transition flex items-center gap-2 font-medium disabled:opacity-50"
                                >
                                    ⏭️ Sonraki Saat
                                </button>
                            )}

                            {simStatus.day_completed && (
                                <button
                                    onClick={nextDay}
                                    disabled={isLoading || simStatus.is_eod_running}
                                    className={`px-4 py-1.5 text-white rounded-lg transition flex items-center gap-2 font-medium ${simStatus.is_eod_running
                                        ? 'bg-gray-500/30 cursor-not-allowed opacity-50'
                                        : 'bg-white/20 hover:bg-white/30 disabled:opacity-50'
                                        }`}
                                >
                                    ▶️ Sonraki Gün
                                </button>
                            )}

                            <button
                                onClick={stopSimulation}
                                disabled={isLoading}
                                className="px-3 py-1.5 bg-red-500/50 hover:bg-red-500/70 text-white rounded-lg transition disabled:opacity-50"
                                title="Simülasyonu Bitir"
                            >
                                ⏹️
                            </button>
                        </>
                    )}
                </div>
            </div>
        </div>
    );
};

export default SimulationBanner;
