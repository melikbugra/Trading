import React from 'react';
import { useSimulation } from '../contexts/SimulationContext';

const SimulationBanner = () => {
    const {
        isSimulationMode,
        simStatus,
        nextHour,
        nextDay,
        stopSimulation,
        isLoading,
        formatSimTime,
    } = useSimulation();

    if (!isSimulationMode) return null;

    const currentTime = simStatus.current_time ? new Date(simStatus.current_time) : null;
    const dayName = currentTime?.toLocaleDateString('tr-TR', { weekday: 'long' });
    const dateStr = currentTime?.toLocaleDateString('tr-TR', { day: '2-digit', month: '2-digit', year: 'numeric' });
    const timeStr = currentTime?.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' });

    return (
        <div className={`w-full ${simStatus.day_completed
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
                <div className="flex items-center gap-4">
                    {/* Simulation Label */}
                    <div className="flex items-center gap-2">
                        <span className="text-xl">🧪</span>
                        <span className="font-semibold text-white">SİMÜLASYON</span>
                    </div>

                    {/* Divider */}
                    <div className="h-6 w-px bg-white/30" />

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
                </div>

                {/* Right: Controls */}
                <div className="flex items-center gap-2">
                    {/* Next Hour: Show when hour scan done and day not completed */}
                    {simStatus.hour_completed && !simStatus.day_completed && !simStatus.is_eod_running && (
                        <button
                            onClick={nextHour}
                            disabled={isLoading || simStatus.is_scanning}
                            className="px-4 py-1.5 bg-blue-500/50 hover:bg-blue-500/70 text-white rounded-lg transition flex items-center gap-2 font-medium disabled:opacity-50"
                        >
                            ⏭️ Sonraki Saat
                        </button>
                    )}

                    {/* Day Completed: Show Next Day button (disabled during EOD) */}
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

                    {/* Stop */}
                    <button
                        onClick={stopSimulation}
                        disabled={isLoading}
                        className="px-3 py-1.5 bg-red-500/50 hover:bg-red-500/70 text-white rounded-lg transition disabled:opacity-50"
                        title="Simülasyonu Bitir"
                    >
                        ⏹️
                    </button>
                </div>
            </div>
        </div>
    );
};

export default SimulationBanner;
