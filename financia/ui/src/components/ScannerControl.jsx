import { useState, useEffect } from 'react';
import { useSimulation } from '../contexts/SimulationContext';
import { useToast } from '../contexts/ToastContext';
import { useWebSocket } from '../contexts/WebSocketContext';

const API_BASE = import.meta.env.VITE_API_BASE || '';

export default function ScannerControl({ config, onUpdate, onScanNow, isScanning }) {
    const { isSimulationMode, simStatus } = useSimulation();
    const { addToast } = useToast();
    const { scanProgress, simScanProgress } = useWebSocket();
    const [editingInterval, setEditingInterval] = useState(false);
    const [tempInterval, setTempInterval] = useState(config.scan_interval_minutes);
    const [simScanning, setSimScanning] = useState(false);
    const [countdown, setCountdown] = useState(null);

    // Countdown timer for simulation mode
    useEffect(() => {
        if (!isSimulationMode || !simStatus.is_active) {
            setCountdown(null);
            return;
        }

        // If paused, day completed, EOD running, or scanning - don't count down
        if (simStatus.is_paused || simStatus.day_completed || simStatus.is_eod_running || simStatus.is_scanning) {
            setCountdown(null);
            return;
        }

        // Start countdown from seconds_per_hour
        const totalSeconds = simStatus.seconds_per_hour || 30;
        setCountdown(totalSeconds);

        const interval = setInterval(() => {
            setCountdown(prev => {
                if (prev === null || prev <= 1) {
                    return totalSeconds; // Reset when reaching 0
                }
                return prev - 1;
            });
        }, 1000);

        return () => clearInterval(interval);
    }, [isSimulationMode, simStatus.is_active, simStatus.is_paused, simStatus.day_completed, simStatus.is_eod_running, simStatus.is_scanning, simStatus.seconds_per_hour]);

    // Manual scan for simulation mode
    const handleSimScanNow = async () => {
        setSimScanning(true);
        try {
            const res = await fetch(`${API_BASE}/simulation/scan-now`, {
                method: 'POST'
            });
            if (res.ok) {
                addToast('Simülasyon taraması tamamlandı', 'success');
            } else {
                const err = await res.json();
                addToast(err.detail || 'Tarama başarısız', 'error');
            }
        } catch (err) {
            addToast('Tarama hatası: ' + err.message, 'error');
        } finally {
            setSimScanning(false);
        }
    };

    // In simulation mode, show a minimal info bar with countdown and manual scan button
    if (isSimulationMode) {
        const isPaused = simStatus.is_paused || simStatus.day_completed;
        const isEodRunning = simStatus.is_eod_running;
        const isScanningNow = simStatus.is_scanning;

        // Calculate progress percentage for simulation
        const simProgressPercent = simScanProgress && simScanProgress.total > 0
            ? Math.round((simScanProgress.current / simScanProgress.total) * 100)
            : 0;

        return (
            <div className="bg-purple-900/30 border border-purple-700/50 rounded-lg p-3 sm:p-4">
                <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-3 flex-wrap">
                        <span className="text-xl">🧪</span>
                        <span className="text-purple-300 font-medium text-sm sm:text-base">
                            Simülasyon Modu Aktif
                        </span>
                        {/* Countdown timer */}
                        {countdown !== null && !isPaused && !isEodRunning && !isScanningNow && (
                            <span className="bg-purple-800/50 px-2 py-1 rounded text-purple-200 text-xs sm:text-sm font-mono flex items-center gap-1">
                                ⏱️ <span className="font-bold">{countdown}s</span>
                                <span className="text-purple-400/70 hidden sm:inline">/ sonraki saat</span>
                            </span>
                        )}
                        {isScanningNow && !isEodRunning && (
                            <div className="flex items-center gap-2">
                                <span className="bg-orange-800/50 px-2 py-1 rounded text-orange-200 text-xs sm:text-sm flex items-center gap-1">
                                    <span className="animate-spin">🔄</span> Taranıyor...
                                </span>
                                {/* Progress bar for simulation scan */}
                                {simScanProgress && simScanProgress.total > 0 && (
                                    <div className="flex items-center gap-2">
                                        <div className="w-24 sm:w-32 bg-gray-700 rounded-full h-2">
                                            <div
                                                className="bg-orange-500 h-2 rounded-full transition-all duration-300"
                                                style={{ width: `${simProgressPercent}%` }}
                                            />
                                        </div>
                                        <span className="text-orange-200 text-xs font-mono">
                                            {simScanProgress.current}/{simScanProgress.total}
                                        </span>
                                        <span className="text-orange-300/70 text-xs hidden sm:inline">
                                            {simScanProgress.ticker}
                                        </span>
                                    </div>
                                )}
                            </div>
                        )}
                        {isEodRunning && (
                            <span className="bg-blue-800/50 px-2 py-1 rounded text-blue-200 text-xs sm:text-sm flex items-center gap-1">
                                <span className="animate-spin">📊</span> Gün Sonu Analizi...
                            </span>
                        )}
                        {isPaused && !isEodRunning && !isScanningNow && (
                            <span className="bg-yellow-800/50 px-2 py-1 rounded text-yellow-200 text-xs sm:text-sm">
                                ⏸️ {simStatus.day_completed ? 'Gün Tamamlandı' : 'Duraklatıldı'}
                            </span>
                        )}
                        <span className="text-purple-400/70 text-xs hidden lg:inline">
                            — {simStatus.seconds_per_hour}sn/saat hızında
                        </span>
                    </div>
                    <button
                        onClick={handleSimScanNow}
                        disabled={simScanning || isScanningNow}
                        className={`px-3 sm:px-4 py-1.5 sm:py-2 rounded font-bold text-xs sm:text-sm transition-all flex items-center gap-1 sm:gap-2 ${simScanning
                            ? 'bg-gray-600 text-gray-400 cursor-not-allowed'
                            : 'bg-purple-600 hover:bg-purple-700 text-white'
                            }`}
                    >
                        <span className={simScanning ? 'animate-spin' : ''}>🔄</span>
                        <span className="hidden sm:inline">{simScanning ? 'Taranıyor...' : 'Manuel Tara'}</span>
                    </button>
                </div>
            </div>
        );
    }

    // Email notification settings (synced with backend via config prop)
    const emailNotifications = config.email_notifications || {
        triggered: true,
        entryReached: true
    };

    // Update email notification settings via API
    const updateEmailNotifications = (key, value) => {
        const updated = { ...emailNotifications, [key]: value };
        onUpdate({ email_notifications: updated });
    };

    const toggleScanner = () => {
        onUpdate({ is_running: !config.is_running });
    };

    const saveInterval = () => {
        onUpdate({ scan_interval_minutes: parseInt(tempInterval) || 5 });
        setEditingInterval(false);
    };

    const formatLastScan = (dateStr) => {
        if (!dateStr) return 'Hiç taranmadı';
        const date = new Date(dateStr);
        return date.toLocaleTimeString('tr-TR', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            timeZone: 'Europe/Istanbul'
        });
    };

    // Calculate progress percentage for live mode
    const liveProgressPercent = scanProgress && scanProgress.total > 0
        ? Math.round((scanProgress.current / scanProgress.total) * 100)
        : 0;

    return (
        <div className="bg-gray-900/50 border border-gray-800 rounded-lg p-3 sm:p-4">
            <div className="flex flex-wrap items-center gap-3 sm:gap-4">
                {/* Scanner Status */}
                <div className="flex items-center gap-2 sm:gap-4">
                    <div className="flex items-center gap-2">
                        <div className={`w-3 h-3 rounded-full ${config.is_running ? 'bg-green-500 animate-pulse' : 'bg-gray-600'}`} />
                        <span className="text-gray-300 font-medium text-sm sm:text-base">
                            Tarama
                        </span>
                    </div>

                    <button
                        onClick={toggleScanner}
                        className={`px-3 sm:px-4 py-1.5 sm:py-2 rounded font-bold text-xs sm:text-sm transition-colors ${config.is_running
                            ? 'bg-red-600 hover:bg-red-700 text-white'
                            : 'bg-green-600 hover:bg-green-700 text-white'
                            }`}
                    >
                        {config.is_running ? '⏹ Durdur' : '▶️ Başlat'}
                    </button>
                </div>

                {/* Interval Setting */}
                <div className="flex items-center gap-2 sm:gap-3">
                    <span className="text-gray-400 text-xs sm:text-sm hidden sm:inline">Aralık:</span>
                    {editingInterval ? (
                        <div className="flex items-center gap-1 sm:gap-2">
                            <select
                                value={tempInterval}
                                onChange={(e) => setTempInterval(e.target.value)}
                                className="bg-gray-800 border border-gray-700 text-white px-2 sm:px-3 py-1 rounded text-xs sm:text-sm"
                            >
                                <option value="1">1 dk</option>
                                <option value="5">5 dk</option>
                                <option value="15">15 dk</option>
                                <option value="30">30 dk</option>
                                <option value="60">1 saat</option>
                            </select>
                            <button
                                onClick={saveInterval}
                                className="px-2 sm:px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white rounded text-xs sm:text-sm"
                            >
                                ✓
                            </button>
                            <button
                                onClick={() => setEditingInterval(false)}
                                className="px-2 sm:px-3 py-1 bg-gray-700 hover:bg-gray-600 text-white rounded text-xs sm:text-sm"
                            >
                                ✕
                            </button>
                        </div>
                    ) : (
                        <button
                            onClick={() => {
                                setTempInterval(config.scan_interval_minutes);
                                setEditingInterval(true);
                            }}
                            className="px-2 sm:px-3 py-1 bg-gray-800 hover:bg-gray-700 text-white rounded text-xs sm:text-sm border border-gray-700"
                        >
                            {config.scan_interval_minutes} dk 📝
                        </button>
                    )}
                </div>

                {/* Manual Scan */}
                <div className="flex items-center gap-2 sm:gap-3">
                    <span className="text-gray-500 text-xs hidden md:inline">
                        Son: {formatLastScan(config.last_scan_at)}
                    </span>
                    <button
                        onClick={onScanNow}
                        disabled={isScanning}
                        className={`px-3 sm:px-4 py-1.5 sm:py-2 rounded font-bold text-xs sm:text-sm transition-all flex items-center gap-1 sm:gap-2 ${isScanning
                            ? 'bg-gray-600 text-gray-400 cursor-not-allowed'
                            : 'bg-blue-600 hover:bg-blue-700 text-white'
                            }`}
                    >
                        <span className={isScanning ? 'animate-spin' : ''}>🔄</span>
                        <span className="hidden sm:inline">{isScanning ? 'Taranıyor...' : 'Şimdi Tara'}</span>
                    </button>
                    {/* Progress bar for live scan */}
                    {isScanning && scanProgress && scanProgress.total > 0 && (
                        <div className="flex items-center gap-2">
                            <div className="w-20 sm:w-28 bg-gray-700 rounded-full h-2">
                                <div
                                    className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                                    style={{ width: `${liveProgressPercent}%` }}
                                />
                            </div>
                            <span className="text-blue-200 text-xs font-mono">
                                {scanProgress.current}/{scanProgress.total}
                            </span>
                            <span className="text-blue-300/70 text-xs hidden lg:inline">
                                {scanProgress.ticker}
                            </span>
                        </div>
                    )}
                </div>

                {/* Email Notification Settings */}
                <div className="flex items-center gap-2 sm:gap-3 ml-auto">
                    <span className="text-gray-400 text-xs sm:text-sm hidden lg:inline">📧</span>
                    <button
                        onClick={() => updateEmailNotifications('triggered', !emailNotifications.triggered)}
                        className={`px-2 sm:px-3 py-1 sm:py-1.5 rounded text-xs font-medium transition-colors flex items-center gap-1 ${emailNotifications.triggered
                            ? 'bg-orange-600/80 text-white'
                            : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
                            }`}
                        title="Sinyal tetiklendiğinde e-posta bildirimi"
                    >
                        <span>{emailNotifications.triggered ? '🔔' : '🔕'}</span>
                        <span className="hidden sm:inline">Tetiklenen</span>
                    </button>
                    <button
                        onClick={() => updateEmailNotifications('entryReached', !emailNotifications.entryReached)}
                        className={`px-2 sm:px-3 py-1 sm:py-1.5 rounded text-xs font-medium transition-colors flex items-center gap-1 ${emailNotifications.entryReached
                            ? 'bg-green-600/80 text-white'
                            : 'bg-gray-700 text-gray-400 hover:bg-gray-600'
                            }`}
                        title="Giriş fiyatına ulaşıldığında e-posta bildirimi"
                    >
                        <span>{emailNotifications.entryReached ? '🔔' : '🔕'}</span>
                        <span className="hidden sm:inline">Giriş</span>
                    </button>
                </div>
            </div>
        </div>
    );
}
