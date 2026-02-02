import React, { useState } from 'react';
import { useSimulation } from '../contexts/SimulationContext';

const SimulationPanel = ({ onClose }) => {
    const { startSimulation, isLoading, error } = useSimulation();

    // Form state
    const [startDate, setStartDate] = useState(() => {
        // Default: 1 month ago
        const date = new Date();
        date.setMonth(date.getMonth() - 1);
        return date.toISOString().split('T')[0];
    });
    const [endDate, setEndDate] = useState(() => {
        // Default: 1 week ago
        const date = new Date();
        date.setDate(date.getDate() - 7);
        return date.toISOString().split('T')[0];
    });
    const [secondsPerHour, setSecondsPerHour] = useState(30);
    const [initialBalance, setInitialBalance] = useState(100000);
    const [localError, setLocalError] = useState(null);

    const handleStart = async () => {
        setLocalError(null);

        // Validate dates
        if (!startDate || !endDate) {
            setLocalError('Lütfen tarih aralığı seçin');
            return;
        }
        if (new Date(startDate) > new Date(endDate)) {
            setLocalError('Başlangıç tarihi bitiş tarihinden önce olmalı');
            return;
        }
        if (new Date(endDate) > new Date()) {
            setLocalError('Bitiş tarihi bugünden sonra olamaz');
            return;
        }
        if (initialBalance < 1000) {
            setLocalError('Minimum bakiye 1.000 TL olmalı');
            return;
        }

        try {
            await startSimulation(startDate, endDate, secondsPerHour, initialBalance);
            onClose?.();
        } catch (err) {
            setLocalError(err.message);
        }
    };

    const speedOptions = [
        { value: 10, label: 'Hızlı', desc: '1 saat = 10 saniye' },
        { value: 30, label: 'Normal', desc: '1 saat = 30 saniye' },
        { value: 60, label: 'Yavaş', desc: '1 saat = 60 saniye' },
        { value: 120, label: 'Çok Yavaş', desc: '1 saat = 2 dakika' },
    ];

    // Calculate estimated time for one trading day (9 hours)
    const estimatedDayTime = (secondsPerHour * 9) / 60;

    return (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-gray-800 rounded-lg shadow-xl w-full max-w-md mx-4">
                {/* Header */}
                <div className="flex items-center justify-between px-6 py-4 border-b border-gray-700">
                    <div className="flex items-center gap-3">
                        <span className="text-2xl">🎮</span>
                        <h2 className="text-xl font-semibold text-white">Simülasyon Modu</h2>
                    </div>
                    <button
                        onClick={onClose}
                        className="text-gray-400 hover:text-white transition"
                    >
                        ✕
                    </button>
                </div>

                {/* Content */}
                <div className="p-6 space-y-6">
                    {/* Description */}
                    <p className="text-gray-400 text-sm">
                        Geçmiş verileri canlı piyasa gibi oynatarak strateji pratik yapın.
                        Saatlik veriler üzerinden simülasyon yapılır.
                    </p>

                    {/* Date Range */}
                    <div className="space-y-4">
                        <div>
                            <label className="block text-sm font-medium text-gray-300 mb-2">
                                📅 Başlangıç Tarihi
                            </label>
                            <input
                                type="date"
                                value={startDate}
                                onChange={(e) => setStartDate(e.target.value)}
                                max={endDate || undefined}
                                className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                            />
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-gray-300 mb-2">
                                📅 Bitiş Tarihi
                            </label>
                            <input
                                type="date"
                                value={endDate}
                                onChange={(e) => setEndDate(e.target.value)}
                                min={startDate || undefined}
                                max={new Date().toISOString().split('T')[0]}
                                className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                            />
                        </div>
                    </div>

                    {/* Speed Selection */}
                    <div>
                        <label className="block text-sm font-medium text-gray-300 mb-3">
                            ⚡ Simülasyon Hızı
                        </label>
                        <div className="grid grid-cols-2 gap-2">
                            {speedOptions.map((option) => (
                                <button
                                    key={option.value}
                                    onClick={() => setSecondsPerHour(option.value)}
                                    className={`p-3 rounded-lg border transition text-left ${secondsPerHour === option.value
                                        ? 'border-blue-500 bg-blue-500/20 text-blue-400'
                                        : 'border-gray-600 bg-gray-700 text-gray-300 hover:border-gray-500'
                                        }`}
                                >
                                    <div className="font-medium">{option.label}</div>
                                    <div className="text-xs text-gray-400">{option.desc}</div>
                                </button>
                            ))}
                        </div>
                        <p className="mt-2 text-xs text-gray-500">
                            Tahmini süre: 1 işlem günü ≈ {estimatedDayTime.toFixed(1)} dakika
                        </p>
                    </div>

                    {/* Initial Balance */}
                    <div>
                        <label className="block text-sm font-medium text-gray-300 mb-2">
                            💰 Başlangıç Bakiyesi (TL)
                        </label>
                        <input
                            type="number"
                            value={initialBalance}
                            onChange={(e) => setInitialBalance(Number(e.target.value))}
                            min={1000}
                            step={10000}
                            className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                        <div className="flex gap-2 mt-2">
                            {[50000, 100000, 250000, 500000].map((amount) => (
                                <button
                                    key={amount}
                                    onClick={() => setInitialBalance(amount)}
                                    className={`flex-1 px-2 py-1 text-xs rounded border transition ${initialBalance === amount
                                        ? 'border-blue-500 bg-blue-500/20 text-blue-400'
                                        : 'border-gray-600 bg-gray-700 text-gray-400 hover:border-gray-500'
                                        }`}
                                >
                                    {(amount / 1000).toFixed(0)}K
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Error Message */}
                    {(localError || error) && (
                        <div className="p-3 bg-red-500/20 border border-red-500/50 rounded-lg text-red-400 text-sm">
                            ⚠️ {localError || error}
                        </div>
                    )}

                    {/* Info Box */}
                    <div className="p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-lg text-yellow-400 text-sm">
                        <strong>Not:</strong> Simülasyon başladığında mevcut simülasyon verileri silinir.
                        Hafta sonları otomatik olarak atlanır.
                    </div>
                </div>

                {/* Footer */}
                <div className="flex gap-3 px-6 py-4 border-t border-gray-700">
                    <button
                        onClick={onClose}
                        className="flex-1 px-4 py-2 bg-gray-700 text-gray-300 rounded-lg hover:bg-gray-600 transition"
                    >
                        İptal
                    </button>
                    <button
                        onClick={handleStart}
                        disabled={isLoading}
                        className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-500 transition disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                    >
                        {isLoading ? (
                            <>
                                <span className="animate-spin">⏳</span>
                                Başlatılıyor...
                            </>
                        ) : (
                            <>
                                🚀 Simülasyonu Başlat
                            </>
                        )}
                    </button>
                </div>
            </div>
        </div>
    );
};

export default SimulationPanel;
