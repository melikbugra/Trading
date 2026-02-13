import React, { useState, useEffect } from 'react';
import { useSimulation } from '../contexts/SimulationContext';

const API_BASE = import.meta.env.VITE_API_BASE || '';

const SimulationPanel = ({ onClose }) => {
    const { startSimulation, startBacktest, isLoading, error } = useSimulation();

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
    const [initialBalance, setInitialBalance] = useState(100000);
    const [localError, setLocalError] = useState(null);

    // Backtest mode
    const [isBacktest, setIsBacktest] = useState(false);
    const [strategyTypes, setStrategyTypes] = useState([]);
    const [selectedStrategyTypes, setSelectedStrategyTypes] = useState([]);
    const [loadingStrategies, setLoadingStrategies] = useState(false);

    // Fetch strategies when backtest mode is enabled
    useEffect(() => {
        if (isBacktest) {
            fetchStrategies();
        }
    }, [isBacktest]);

    const fetchStrategies = async () => {
        setLoadingStrategies(true);
        try {
            // Fetch Python-defined strategy types (from STRATEGY_REGISTRY)
            const res = await fetch(`${API_BASE}/strategies/available-types`);
            if (res.ok) {
                const data = await res.json();
                setStrategyTypes(data);
                // Auto-select all
                setSelectedStrategyTypes(data.map(s => s.type));
            }
        } catch (err) {
            console.error('Failed to fetch strategy types:', err);
        } finally {
            setLoadingStrategies(false);
        }
    };

    const toggleStrategy = (type) => {
        setSelectedStrategyTypes(prev =>
            prev.includes(type)
                ? prev.filter(t => t !== type)
                : [...prev, type]
        );
    };

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

        if (isBacktest) {
            if (selectedStrategyTypes.length === 0) {
                setLocalError('En az bir strateji seçmelisiniz');
                return;
            }
            try {
                await startBacktest(startDate, endDate, initialBalance, selectedStrategyTypes);
                onClose?.();
            } catch (err) {
                setLocalError(err.message);
            }
        } else {
            try {
                await startSimulation(startDate, endDate, 30, initialBalance);
                onClose?.();
            } catch (err) {
                setLocalError(err.message);
            }
        }
    };

    return (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-gray-800 rounded-lg shadow-xl w-full max-w-md mx-4">
                {/* Header */}
                <div className="flex items-center justify-between px-6 py-4 border-b border-gray-700">
                    <div className="flex items-center gap-3">
                        <span className="text-2xl">{isBacktest ? '⚡' : '🎮'}</span>
                        <h2 className="text-xl font-semibold text-white">
                            {isBacktest ? 'Backtest Modu' : 'Simülasyon Modu'}
                        </h2>
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
                    {/* Mode Toggle */}
                    <div className="flex items-center gap-3 p-3 bg-gray-700/50 rounded-lg">
                        <label className="flex items-center gap-2 cursor-pointer select-none">
                            <input
                                type="checkbox"
                                checked={isBacktest}
                                onChange={(e) => setIsBacktest(e.target.checked)}
                                className="w-4 h-4 rounded border-gray-500 text-yellow-500 focus:ring-yellow-500 bg-gray-600"
                            />
                            <span className="text-yellow-400 font-medium">⚡ Backtest Modu</span>
                        </label>
                        <span className="text-gray-400 text-xs">
                            {isBacktest
                                ? 'Otomatik al-sat, hızlandırılmış simülasyon'
                                : 'Manuel kontrollü simülasyon'}
                        </span>
                    </div>

                    {/* Strategy Selection (Backtest only) */}
                    {isBacktest && (
                        <div>
                            <label className="block text-sm font-medium text-gray-300 mb-2">
                                📋 Test Edilecek Stratejiler
                            </label>
                            {loadingStrategies ? (
                                <div className="text-gray-400 text-sm p-3 bg-gray-700/50 rounded-lg">
                                    <span className="animate-spin inline-block mr-2">⏳</span>
                                    Stratejiler yükleniyor...
                                </div>
                            ) : strategyTypes.length === 0 ? (
                                <div className="text-red-400 text-sm p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
                                    ⚠️ Tanımlı strateji bulunamadı.
                                </div>
                            ) : (
                                <div className="space-y-1 max-h-40 overflow-y-auto bg-gray-700/30 rounded-lg p-2">
                                    {strategyTypes.map((s) => (
                                        <label
                                            key={s.type}
                                            className={`flex items-center gap-2 p-2 rounded cursor-pointer transition ${selectedStrategyTypes.includes(s.type)
                                                ? 'bg-yellow-500/10 border border-yellow-500/30'
                                                : 'hover:bg-gray-600/50 border border-transparent'
                                                }`}
                                        >
                                            <input
                                                type="checkbox"
                                                checked={selectedStrategyTypes.includes(s.type)}
                                                onChange={() => toggleStrategy(s.type)}
                                                className="w-4 h-4 rounded border-gray-500 text-yellow-500 focus:ring-yellow-500 bg-gray-600"
                                            />
                                            <div className="flex-1 min-w-0">
                                                <span className="text-white text-sm font-medium">{s.name}</span>
                                                <span className="text-gray-400 text-xs ml-2">({s.type})</span>
                                            </div>
                                        </label>
                                    ))}
                                    {strategyTypes.length > 1 && (
                                        <div className="flex gap-2 mt-1 pt-1 border-t border-gray-600">
                                            <button
                                                onClick={() => setSelectedStrategyTypes(strategyTypes.map(s => s.type))}
                                                className="text-xs text-blue-400 hover:text-blue-300"
                                            >
                                                Tümünü Seç
                                            </button>
                                            <button
                                                onClick={() => setSelectedStrategyTypes([])}
                                                className="text-xs text-gray-400 hover:text-gray-300"
                                            >
                                                Temizle
                                            </button>
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    )}

                    {/* Description */}
                    <p className="text-gray-400 text-sm">
                        {isBacktest
                            ? 'Seçilen stratejileri geçmiş verilerle otomatik test edin. Sinyal gelince 1 lot alınır, SL/TP değince satılır.'
                            : 'Geçmiş verileri canlı piyasa gibi oynatarak strateji pratik yapın. Her saatte otomatik tarama yapılır, sonraki saate siz geçersiniz.'
                        }
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
                    <div className={`p-3 ${isBacktest ? 'bg-yellow-500/10 border-yellow-500/30' : 'bg-yellow-500/10 border-yellow-500/30'} border rounded-lg text-yellow-400 text-sm`}>
                        {isBacktest ? (
                            <>
                                <strong>Backtest:</strong> Tüm tarih aralığı otomatik olarak hızlandırılmış şekilde işlenecek.
                                Her sinyal tetiklendiğinde 1 lot alınır, SL/TP değdiğinde otomatik satılır.
                                Sonuçları Geçmiş sekmesinden inceleyebilirsiniz.
                            </>
                        ) : (
                            <>
                                <strong>Not:</strong> Simülasyon başladığında mevcut simülasyon verileri silinir.
                                Hafta sonları otomatik olarak atlanır.
                            </>
                        )}
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
                        disabled={isLoading || (isBacktest && selectedStrategyTypes.length === 0)}
                        className={`flex-1 px-4 py-2 ${isBacktest ? 'bg-yellow-600 hover:bg-yellow-500' : 'bg-blue-600 hover:bg-blue-500'} text-white rounded-lg transition disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2`}
                    >
                        {isLoading ? (
                            <>
                                <span className="animate-spin">⏳</span>
                                Başlatılıyor...
                            </>
                        ) : isBacktest ? (
                            <>
                                ⚡ Backtest Başlat
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
