import { useState } from 'react';

export default function ScannerControl({ config, onUpdate, onScanNow, isScanning }) {
    const [editingInterval, setEditingInterval] = useState(false);
    const [tempInterval, setTempInterval] = useState(config.scan_interval_minutes);

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
