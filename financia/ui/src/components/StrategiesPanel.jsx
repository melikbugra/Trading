import { useState, useEffect } from 'react';
import { useToast } from '../contexts/ToastContext';
import { useSimulation } from '../contexts/SimulationContext';
import ChartModal from './ChartModal';

const API_BASE = import.meta.env.VITE_API_BASE || '';

// BIST100 hisse listesi
const BIST100_TICKERS = [
    'AEFES', 'AFYON', 'AGROT', 'AKBNK', 'AKFGY', 'AKFYE', 'AKSA', 'AKSEN', 'ALARK', 'ALFAS',
    'ARCLK', 'ASELS', 'AYDEM', 'AYGAZ', 'BAGFS', 'BERA', 'BIMAS', 'BIOEN', 'BRISA', 'BRSAN',
    'BRYAT', 'BTCIM', 'BUCIM', 'CCOLA', 'CEMTS', 'CIMSA', 'DOAS', 'DOHOL', 'ECILC', 'EGEEN',
    'EKGYO', 'ENERY', 'ENJSA', 'ENKAI', 'EREGL', 'EUPWR', 'EUREN', 'FROTO', 'GARAN', 'GENIL',
    'GESAN', 'GLYHO', 'GUBRF', 'HALKB', 'HEKTS', 'ISCTR', 'ISGYO', 'ISMEN', 'KAYSE', 'KCAER',
    'KCHOL', 'KLSER', 'KMPUR', 'KONTR', 'KONYA', 'KORDS', 'KRDMD', 'MAVI',
    'MGROS', 'MPARK', 'ODAS', 'OTKAR', 'OYAKC', 'PETKM', 'PGSUS', 'QUAGR', 'SAHOL', 'SASA',
    'SDTTR', 'SELEC', 'SISE', 'SKBNK', 'SMRTG', 'SOKM', 'TAVHL', 'TCELL', 'THYAO', 'TKFEN',
    'TKNSA', 'TOASO', 'TRGYO', 'TTKOM', 'TTRAK', 'TUKAS', 'TUPRS', 'TURSG', 'ULKER', 'VAKBN',
    'VESBE', 'VESTL', 'YEOTK', 'YKBNK', 'YYLGD', 'ZOREN'
];

// BIST30 hisse listesi (en büyük 30)
const BIST30_TICKERS = [
    'AKBNK', 'ARCLK', 'ASELS', 'BIMAS', 'EKGYO', 'EREGL', 'FROTO', 'GARAN', 'GUBRF', 'HALKB',
    'ISCTR', 'KCHOL', 'KOZAL', 'KRDMD', 'MGROS', 'PGSUS', 'SAHOL', 'SASA', 'SISE', 'TAVHL',
    'TCELL', 'THYAO', 'TKFEN', 'TOASO', 'TTKOM', 'TUPRS', 'VAKBN', 'VESTL', 'YKBNK', 'ENKAI'
];

// En popüler 10 kripto para
const TOP_CRYPTO_TICKERS = [
    'BTC', 'ETH', 'BNB', 'XRP', 'SOL', 'ADA', 'DOGE', 'AVAX', 'DOT', 'LINK'
];

export default function StrategiesPanel({ strategies, onRefresh }) {
    const { addToast } = useToast();
    const { isSimulationMode, isStatusLoaded } = useSimulation();
    const [availableTypes, setAvailableTypes] = useState([]);
    const [watchlist, setWatchlist] = useState([]);
    const [showAddModal, setShowAddModal] = useState(false);
    const [editingStrategy, setEditingStrategy] = useState(null);
    const [showAddTickerModal, setShowAddTickerModal] = useState(null); // strategy id
    const [addingAllBist, setAddingAllBist] = useState(false); // bulk add loading state
    const [addingBist30, setAddingBist30] = useState(false); // BIST30 bulk add loading
    const [addingCrypto, setAddingCrypto] = useState(false); // Crypto bulk add loading
    const [deletingAllTickers, setDeletingAllTickers] = useState(null); // strategy id being cleared
    const [chartModal, setChartModal] = useState(null); // { ticker, market, strategyId }
    const [confirmModal, setConfirmModal] = useState(null); // { title, message, onConfirm }

    // Strategy form state
    const [formType, setFormType] = useState('');
    const [formRR, setFormRR] = useState(2.0);
    const [formParams, setFormParams] = useState({});
    const [formHorizon, setFormHorizon] = useState('short');
    const [formError, setFormError] = useState('');

    // Add ticker form state
    const [newTicker, setNewTicker] = useState('');
    const [newMarket, setNewMarket] = useState('bist100');
    const [addTickerError, setAddTickerError] = useState('');

    // API prefixes based on mode - use functions to get fresh values
    const getStrategiesApi = () => isSimulationMode ? `${API_BASE}/simulation/strategies` : `${API_BASE}/strategies`;
    const getWatchlistApi = () => isSimulationMode ? `${API_BASE}/simulation/watchlist` : `${API_BASE}/strategies/watchlist`;
    const getTypesApi = () => isSimulationMode ? `${API_BASE}/simulation/strategies/available-types` : `${API_BASE}/strategies/available-types`;

    // Fetch available strategy types
    const fetchTypes = async () => {
        const endpoint = getTypesApi();
        console.log('[StrategiesPanel] fetchTypes, endpoint:', endpoint);
        try {
            const res = await fetch(endpoint);
            if (res.ok) {
                const data = await res.json();
                setAvailableTypes(data);
            } else {
                console.error('Failed to fetch types, status:', res.status);
            }
        } catch (err) {
            console.error('Failed to fetch strategy types:', err);
        }
    };

    // Fetch watchlist
    const fetchWatchlist = async () => {
        const endpoint = getWatchlistApi();
        console.log('[StrategiesPanel] fetchWatchlist, endpoint:', endpoint);
        try {
            const res = await fetch(endpoint);
            if (res.ok) {
                const data = await res.json();
                setWatchlist(data);
            }
        } catch (err) {
            console.error('Failed to fetch watchlist:', err);
        }
    };

    // Fetch data when simulation status is loaded or mode changes
    useEffect(() => {
        if (isStatusLoaded) {
            console.log('[StrategiesPanel] Mode changed, isSimulationMode:', isSimulationMode);
            fetchTypes();
            fetchWatchlist();
        }
    }, [isStatusLoaded, isSimulationMode]);

    // Get watchlist items for a specific strategy
    const getWatchlistForStrategy = (strategyId) => {
        return watchlist.filter(item => item.strategy_id === strategyId);
    };

    const openAddModal = () => {
        fetchTypes(); // Stratejileri tekrar yükle
        setFormType('');
        setFormRR(2.0);
        setFormParams({});
        setFormHorizon('short');
        setFormError('');
        setEditingStrategy(null);
        setShowAddModal(true);
    };

    const openEditModal = (strategy) => {
        setFormType(strategy.strategy_type);
        setFormRR(strategy.risk_reward_ratio);
        setFormParams(strategy.params || {});
        setFormHorizon(strategy.horizon || 'short');
        setFormError('');
        setEditingStrategy(strategy);
        setShowAddModal(true);
    };

    const handleTypeChange = (type) => {
        setFormType(type);
        const typeInfo = availableTypes.find(t => t.type === type);
        if (typeInfo) {
            setFormParams(typeInfo.default_params || {});
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setFormError('');

        if (!formType) {
            setFormError('Strateji tipi seçiniz');
            return;
        }

        // Seçilen tipten isim ve açıklamayı al
        const typeInfo = availableTypes.find(t => t.type === formType);
        const payload = {
            name: typeInfo?.name || formType,
            description: typeInfo?.description || '',
            strategy_type: formType,
            risk_reward_ratio: parseFloat(formRR),
            params: formParams,
            horizon: formHorizon
        };

        try {
            let res;
            if (editingStrategy) {
                res = await fetch(`${getStrategiesApi()}/${editingStrategy.id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
            } else {
                res = await fetch(getStrategiesApi(), {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
            }

            if (res.ok) {
                setShowAddModal(false);
                onRefresh();
            } else {
                const data = await res.json();
                setFormError(data.detail || 'İşlem başarısız');
            }
        } catch (err) {
            setFormError('Bağlantı hatası');
        }
    };

    const deleteStrategy = async (strategyId, confirmed = false) => {
        if (!confirmed) {
            setConfirmModal({
                title: '⚠️ Strateji Sil',
                message: 'Stratejiyi silmek istediğinize emin misiniz? İlgili ticker\'lar ve sinyaller de silinecek.',
                onConfirm: () => {
                    setConfirmModal(null);
                    deleteStrategy(strategyId, true);
                }
            });
            return;
        }

        try {
            await fetch(`${getStrategiesApi()}/${strategyId}`, { method: 'DELETE' });
            onRefresh();
            fetchWatchlist();
        } catch (err) {
            console.error('Failed to delete strategy:', err);
        }
    };

    const toggleStrategy = async (strategy) => {
        try {
            await fetch(`${getStrategiesApi()}/${strategy.id}/toggle`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ is_active: !strategy.is_active })
            });
            onRefresh();
        } catch (err) {
            console.error('Failed to toggle strategy:', err);
        }
    };

    // Ticker CRUD
    const openAddTickerModal = (strategyId) => {
        setNewTicker('');
        setNewMarket('bist100');
        setAddTickerError('');
        setShowAddTickerModal(strategyId);
    };

    const addTicker = async (e) => {
        e.preventDefault();
        setAddTickerError('');

        if (!newTicker) {
            setAddTickerError('Ticker zorunludur');
            return;
        }

        let formattedTicker = newTicker.toUpperCase();
        if (newMarket === 'bist100' && !formattedTicker.endsWith('.IS')) {
            formattedTicker += '.IS';
        } else if (newMarket === 'binance' && !formattedTicker.endsWith('TRY')) {
            formattedTicker += 'TRY';
        }

        try {
            const res = await fetch(getWatchlistApi(), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    ticker: formattedTicker,
                    market: newMarket,
                    strategy_id: showAddTickerModal
                })
            });

            if (res.ok) {
                setShowAddTickerModal(null);
                fetchWatchlist();
            } else {
                const data = await res.json();
                setAddTickerError(data.detail || 'Eklenemedi');
            }
        } catch (err) {
            setAddTickerError('Bağlantı hatası');
        }
    };

    const removeTicker = async (itemId) => {
        try {
            await fetch(`${getWatchlistApi()}/${itemId}`, { method: 'DELETE' });
            fetchWatchlist();
        } catch (err) {
            console.error('Failed to remove ticker:', err);
        }
    };

    // Helper for delay
    const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms));

    const addAllBist100 = async () => {
        if (!showAddTickerModal) return;

        setAddingAllBist(true);
        setAddTickerError('');

        let added = 0;
        let skipped = 0;

        // Batch size for parallel requests
        const batchSize = 5;

        for (let i = 0; i < BIST100_TICKERS.length; i += batchSize) {
            const batch = BIST100_TICKERS.slice(i, i + batchSize);

            const promises = batch.map(async (ticker) => {
                const formattedTicker = ticker + '.IS';
                try {
                    const res = await fetch(getWatchlistApi(), {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            ticker: formattedTicker,
                            market: 'bist100',
                            strategy_id: showAddTickerModal
                        })
                    });

                    if (res.ok) {
                        return 'added';
                    } else {
                        return 'skipped'; // Muhtemelen zaten ekli
                    }
                } catch (err) {
                    return 'skipped';
                }
            });

            const results = await Promise.all(promises);
            results.forEach(r => {
                if (r === 'added') added++;
                else skipped++;
            });

            // Rate limiting between batches
            if (i + batchSize < BIST100_TICKERS.length) {
                await delay(100);
            }
        }

        setAddingAllBist(false);
        fetchWatchlist();
        setShowAddTickerModal(null);
        addToast(`✅ BIST100: ${added} sembol eklendi${skipped > 0 ? `, ${skipped} atlandı` : ''}`, 'success', 5000);
    };

    const addAllBist30 = async () => {
        if (!showAddTickerModal) return;

        setAddingBist30(true);
        setAddTickerError('');

        let added = 0;
        let skipped = 0;

        for (const ticker of BIST30_TICKERS) {
            const formattedTicker = ticker + '.IS';
            try {
                const res = await fetch(getWatchlistApi(), {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        ticker: formattedTicker,
                        market: 'bist100',
                        strategy_id: showAddTickerModal
                    })
                });

                if (res.ok) {
                    added++;
                } else {
                    skipped++;
                }
            } catch (err) {
                skipped++;
            }
        }

        setAddingBist30(false);
        fetchWatchlist();
        setShowAddTickerModal(null);
        addToast(`✅ BIST30: ${added} sembol eklendi${skipped > 0 ? `, ${skipped} atlandı` : ''}`, 'success', 5000);
    };

    const addTopCrypto = async () => {
        if (!showAddTickerModal) return;

        setAddingCrypto(true);
        setAddTickerError('');

        let added = 0;
        let skipped = 0;

        for (const ticker of TOP_CRYPTO_TICKERS) {
            const formattedTicker = ticker + 'TRY';
            try {
                const res = await fetch(getWatchlistApi(), {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        ticker: formattedTicker,
                        market: 'binance',
                        strategy_id: showAddTickerModal
                    })
                });

                if (res.ok) {
                    added++;
                } else {
                    skipped++;
                }
            } catch (err) {
                skipped++;
            }
        }

        setAddingCrypto(false);
        fetchWatchlist();
        setShowAddTickerModal(null);
        addToast(`✅ Top 10 Crypto: ${added} sembol eklendi${skipped > 0 ? `, ${skipped} atlandı` : ''}`, 'success', 5000);
    };

    const deleteAllTickers = async (strategyId, confirmed = false) => {
        const tickers = getWatchlistForStrategy(strategyId);
        if (tickers.length === 0) return;

        if (!confirmed) {
            setConfirmModal({
                title: 'Tüm Sembolleri Sil',
                message: `Bu stratejideki tüm sembolleri (${tickers.length} adet) silmek istediğinize emin misiniz?`,
                onConfirm: () => {
                    setConfirmModal(null);
                    deleteAllTickers(strategyId, true);
                }
            });
            return;
        }

        setDeletingAllTickers(strategyId);

        let deleted = 0;
        for (const item of tickers) {
            try {
                await fetch(`${getWatchlistApi()}/${item.id}`, { method: 'DELETE' });
                deleted++;
            } catch (err) {
                console.error('Failed to delete ticker:', err);
            }
        }

        setDeletingAllTickers(null);
        fetchWatchlist();
        addToast(`🗑️ ${deleted} sembol silindi`, 'info', 3000);
    };

    const toggleTicker = async (itemId) => {
        try {
            await fetch(`${getWatchlistApi()}/${itemId}/toggle`, { method: 'PATCH' });
            fetchWatchlist();
        } catch (err) {
            console.error('Failed to toggle ticker:', err);
        }
    };

    const openChartModal = (ticker, market, strategyId) => {
        setChartModal({ ticker, market, strategyId });
    };

    // Single ticker scan
    const scanSingleTicker = async (ticker, market) => {
        try {
            addToast(`🔍 ${ticker} taranıyor...`, 'info', 2000);
            // Use simulation endpoint if in simulation mode
            const endpoint = isSimulationMode
                ? `${API_BASE}/simulation/scan-ticker/${encodeURIComponent(ticker)}?market=${market}`
                : `${API_BASE}/strategies/scanner/scan-ticker/${encodeURIComponent(ticker)}?market=${market}`;
            const res = await fetch(endpoint, {
                method: 'POST'
            });
            if (res.ok) {
                const data = await res.json();
                if (data.results && data.results.length > 0) {
                    const result = data.results[0];
                    addToast(`✅ ${ticker}: ${result.direction?.toUpperCase() || 'Sinyal yok'} - ${result.status}`, 'success', 4000);
                } else {
                    addToast(`ℹ️ ${ticker}: Sinyal bulunamadı`, 'info', 3000);
                }
            } else {
                addToast(`❌ ${ticker} taranamadı`, 'error', 3000);
            }
        } catch (err) {
            console.error('Failed to scan ticker:', err);
            addToast(`❌ Tarama hatası`, 'error', 3000);
        }
    };

    return (
        <div>
            {/* Header */}
            <div className="flex items-center justify-between mb-4">
                <h2 className="text-base sm:text-lg font-bold text-white">Stratejiler ({strategies.length})</h2>
                <button
                    onClick={openAddModal}
                    className="px-3 sm:px-4 py-1.5 sm:py-2 bg-purple-600 hover:bg-purple-700 text-white rounded font-bold text-xs sm:text-sm transition-colors"
                >
                    ➕ <span className="hidden sm:inline">Strateji </span>Oluştur
                </button>
            </div>

            {/* Strategies List */}
            {strategies.length === 0 ? (
                <div className="bg-gray-900/50 border border-gray-800 rounded-lg p-12 text-center">
                    <div className="text-4xl mb-4">⚙️</div>
                    <div className="text-gray-400">Henüz strateji oluşturulmadı</div>
                    <div className="text-gray-600 text-sm mt-2">
                        Bir strateji oluşturun ve tickerları izlemeye başlayın
                    </div>
                </div>
            ) : (
                <div className="space-y-4">
                    {strategies.map(strategy => {
                        const strategyTickers = getWatchlistForStrategy(strategy.id);

                        return (
                            <div
                                key={strategy.id}
                                className={`bg-gray-900/50 border rounded-lg overflow-hidden transition-colors ${strategy.is_active ? 'border-purple-500/50' : 'border-gray-800 opacity-60'
                                    }`}
                            >
                                {/* Strategy Header */}
                                <div className="p-3 sm:p-4">
                                    <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                                        <div className="flex-1">
                                            <div className="flex flex-wrap items-center gap-2 sm:gap-3 mb-2">
                                                <span className="text-base sm:text-lg font-bold text-white">{strategy.name}</span>
                                                <span className={`px-2 py-0.5 sm:py-1 rounded text-xs ${strategy.is_active
                                                    ? 'bg-green-500/20 text-green-400'
                                                    : 'bg-gray-500/20 text-gray-400'
                                                    }`}>
                                                    {strategy.is_active ? '✓ Aktif' : '⏸ Pasif'}
                                                </span>
                                            </div>

                                            {strategy.description && (
                                                <div className="text-gray-400 text-xs sm:text-sm mb-2 hidden sm:block">{strategy.description}</div>
                                            )}

                                            <div className="flex flex-wrap items-center gap-2 sm:gap-4 text-xs text-gray-500">
                                                <span>📊 1:{strategy.risk_reward_ratio}</span>
                                                <span>⏱️ {
                                                    strategy.horizon === 'short' ? '1h' :
                                                        strategy.horizon === 'short-mid' ? '4h' :
                                                            strategy.horizon === 'medium' ? '1D' :
                                                                strategy.horizon === 'long' ? '1W' : '1h'
                                                }</span>
                                                <span>👁️ {strategyTickers.length}</span>
                                            </div>
                                        </div>

                                        {/* Strategy Actions */}
                                        <div className="flex items-center gap-1 sm:gap-2">
                                            <button
                                                onClick={() => toggleStrategy(strategy)}
                                                className={`px-2 sm:px-3 py-1.5 sm:py-2 rounded text-sm transition-colors ${strategy.is_active
                                                    ? 'bg-yellow-600/20 hover:bg-yellow-600/40 text-yellow-400'
                                                    : 'bg-green-600/20 hover:bg-green-600/40 text-green-400'
                                                    }`}
                                            >
                                                {strategy.is_active ? '⏸' : '▶️'}
                                            </button>
                                            <button
                                                onClick={() => openEditModal(strategy)}
                                                className="px-2 sm:px-3 py-1.5 sm:py-2 bg-blue-600/20 hover:bg-blue-600/40 text-blue-400 rounded text-sm transition-colors"
                                            >
                                                ✏️
                                            </button>
                                            <button
                                                onClick={() => deleteStrategy(strategy.id)}
                                                className="px-2 sm:px-3 py-1.5 sm:py-2 bg-red-600/20 hover:bg-red-600/40 text-red-400 rounded text-sm transition-colors"
                                            >
                                                🗑️
                                            </button>
                                        </div>
                                    </div>
                                </div>

                                {/* Tickers Section */}
                                <div className="border-t border-gray-800 bg-gray-800/30">
                                    <div className="px-3 sm:px-4 py-2 flex items-center justify-between">
                                        <span className="text-gray-400 text-xs sm:text-sm font-medium">
                                            Semboller ({strategyTickers.length})
                                        </span>
                                        <div className="flex items-center gap-2">
                                            {strategyTickers.length > 0 && (
                                                <button
                                                    onClick={() => deleteAllTickers(strategy.id)}
                                                    disabled={deletingAllTickers === strategy.id}
                                                    className="px-2 sm:px-3 py-1 bg-red-600/20 hover:bg-red-600/40 text-red-400 rounded text-xs transition-colors disabled:opacity-50"
                                                    title="Tüm sembolleri sil"
                                                >
                                                    {deletingAllTickers === strategy.id ? '⏳' : '🗑️'} <span className="hidden sm:inline">Tümünü Sil</span>
                                                </button>
                                            )}
                                            <button
                                                onClick={() => openAddTickerModal(strategy.id)}
                                                className="px-2 sm:px-3 py-1 bg-green-600/20 hover:bg-green-600/40 text-green-400 rounded text-xs transition-colors"
                                            >
                                                ➕ <span className="hidden sm:inline">Sembol </span>Ekle
                                            </button>
                                        </div>
                                    </div>

                                    {strategyTickers.length === 0 ? (
                                        <div className="px-3 sm:px-4 pb-3 sm:pb-4 text-center text-gray-600 text-xs sm:text-sm">
                                            Henüz sembol eklenmedi
                                        </div>
                                    ) : (
                                        <div className="px-3 sm:px-4 pb-2 sm:pb-3">
                                            <div className="flex flex-wrap gap-1 sm:gap-2">
                                                {strategyTickers.map(item => (
                                                    <div
                                                        key={item.id}
                                                        className={`flex items-center gap-1 sm:gap-2 px-2 sm:px-3 py-1 sm:py-2 rounded-lg border ${item.is_active
                                                            ? 'bg-gray-800 border-gray-700'
                                                            : 'bg-gray-900 border-gray-800 opacity-50'
                                                            }`}
                                                    >
                                                        <span className={`text-xs ${item.market === 'bist100' ? 'text-red-400' : 'text-yellow-400'
                                                            }`}>
                                                            {item.market === 'bist100' ? '🇹🇷' : '₿'}
                                                        </span>
                                                        <button
                                                            onClick={() => openChartModal(item.ticker, item.market, strategy.id)}
                                                            className="text-white font-mono font-bold text-xs sm:text-sm hover:text-purple-400 transition-colors"
                                                            title="Grafiği görüntüle"
                                                        >
                                                            {item.ticker.replace('.IS', '').replace('TRY', '')}
                                                        </button>
                                                        <div className="flex items-center gap-0.5 sm:gap-1 ml-1 sm:ml-2">
                                                            <button
                                                                onClick={() => scanSingleTicker(item.ticker, item.market)}
                                                                className="p-0.5 sm:p-1 hover:bg-blue-600/30 text-blue-400 rounded transition-colors text-xs sm:text-sm"
                                                                title="Tekli Tara"
                                                            >
                                                                🔍
                                                            </button>
                                                            <button
                                                                onClick={() => toggleTicker(item.id)}
                                                                className={`p-0.5 sm:p-1 rounded transition-colors text-xs sm:text-sm ${item.is_active
                                                                    ? 'hover:bg-yellow-600/30 text-yellow-400'
                                                                    : 'hover:bg-green-600/30 text-green-400'
                                                                    }`}
                                                                title={item.is_active ? 'Duraklat' : 'Aktifleştir'}
                                                            >
                                                                {item.is_active ? '⏸' : '▶️'}
                                                            </button>
                                                            <button
                                                                onClick={() => removeTicker(item.id)}
                                                                className="p-0.5 sm:p-1 hover:bg-red-600/30 text-red-400 rounded transition-colors text-xs sm:text-sm"
                                                                title="Kaldır"
                                                            >
                                                                ✕
                                                            </button>
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}

            {/* Add/Edit Modal */}
            {showAddModal && (
                <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
                    <div className="bg-gray-900 border border-gray-700 rounded-lg p-4 sm:p-6 w-full max-w-lg max-h-[90vh] overflow-y-auto">
                        <h3 className="text-lg font-bold text-white mb-4">
                            {editingStrategy ? 'Stratejiyi Düzenle' : 'Strateji Ekle'}
                        </h3>

                        <form onSubmit={handleSubmit}>
                            <div className="space-y-4">
                                {/* Strategy Type Selection */}
                                {!editingStrategy && (
                                    <div>
                                        <label className="block text-gray-400 text-sm mb-2">Strateji Seçin</label>
                                        {availableTypes.length === 0 ? (
                                            <div className="text-center text-gray-500 py-4">
                                                Strateji tipleri yükleniyor...
                                            </div>
                                        ) : (
                                            <div className="space-y-2">
                                                {availableTypes.map(t => (
                                                    <button
                                                        key={t.type}
                                                        type="button"
                                                        onClick={() => handleTypeChange(t.type)}
                                                        className={`w-full text-left p-3 rounded-lg border transition-colors ${formType === t.type
                                                            ? 'bg-purple-600/30 border-purple-500 text-white'
                                                            : 'bg-gray-800 border-gray-700 text-gray-300 hover:border-gray-600'
                                                            }`}
                                                    >
                                                        <div className="font-bold">{t.name}</div>
                                                        <div className="text-sm text-gray-400 mt-1">{t.description}</div>
                                                    </button>
                                                ))}
                                            </div>
                                        )}
                                    </div>
                                )}

                                {/* Show selected strategy info when editing */}
                                {editingStrategy && (
                                    <div className="p-3 bg-gray-800 rounded-lg border border-gray-700">
                                        <div className="font-bold text-white">{editingStrategy.name}</div>
                                        <div className="text-sm text-gray-400">{editingStrategy.description}</div>
                                    </div>
                                )}

                                {/* Risk/Reward */}
                                <div>
                                    <label className="block text-gray-400 text-sm mb-1">Risk/Reward Oranı</label>
                                    <div className="flex items-center gap-3">
                                        <span className="text-gray-500">1:</span>
                                        <input
                                            type="number"
                                            value={formRR}
                                            onChange={(e) => setFormRR(e.target.value)}
                                            min="0.5"
                                            max="10"
                                            step="0.5"
                                            className="w-24 bg-gray-800 border border-gray-700 text-white px-4 py-2 rounded"
                                        />
                                        <span className="text-gray-500 text-sm">
                                            (TP = Risk × {formRR})
                                        </span>
                                    </div>
                                </div>

                                {/* Timeframe / Horizon */}
                                <div>
                                    <label className="block text-gray-400 text-sm mb-1">Zaman Dilimi</label>
                                    <select
                                        value={formHorizon}
                                        onChange={(e) => setFormHorizon(e.target.value)}
                                        className="w-full bg-gray-800 border border-gray-700 text-white px-4 py-2 rounded"
                                    >
                                        <option value="short">1 Saatlik</option>
                                        <option value="short-mid">4 Saatlik</option>
                                        <option value="medium">Günlük</option>
                                        <option value="long">Haftalık</option>
                                    </select>
                                </div>

                                {/* Parameters */}
                                {Object.keys(formParams).length > 0 && (
                                    <div>
                                        <label className="block text-gray-400 text-sm mb-2">Parametreler</label>
                                        <div className="grid grid-cols-2 gap-3">
                                            {Object.entries(formParams).map(([key, value]) => (
                                                <div key={key}>
                                                    <label className="block text-gray-500 text-xs mb-1">{key}</label>
                                                    <input
                                                        type="number"
                                                        value={value}
                                                        onChange={(e) => setFormParams({
                                                            ...formParams,
                                                            [key]: parseFloat(e.target.value)
                                                        })}
                                                        className="w-full bg-gray-800 border border-gray-700 text-white px-3 py-1 rounded text-sm"
                                                    />
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {formError && (
                                    <div className="text-red-400 text-sm">{formError}</div>
                                )}
                            </div>

                            <div className="flex gap-3 mt-6">
                                <button
                                    type="button"
                                    onClick={() => setShowAddModal(false)}
                                    className="flex-1 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded font-bold text-sm transition-colors"
                                >
                                    İptal
                                </button>
                                <button
                                    type="submit"
                                    className="flex-1 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded font-bold text-sm transition-colors"
                                >
                                    {editingStrategy ? 'Güncelle' : 'Oluştur'}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            {/* Add Ticker Modal */}
            {showAddTickerModal && (
                <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
                    <div className="bg-gray-900 border border-gray-700 rounded-lg p-4 sm:p-6 w-full max-w-md">
                        <h3 className="text-lg font-bold text-white mb-4">Sembol Ekle</h3>

                        <form onSubmit={addTicker}>
                            <div className="space-y-4">
                                <div>
                                    <label className="block text-gray-400 text-sm mb-1">Market</label>
                                    <div className="flex gap-2">
                                        <button
                                            type="button"
                                            onClick={() => setNewMarket('bist100')}
                                            className={`flex-1 px-4 py-2 rounded font-bold text-sm transition-colors ${newMarket === 'bist100'
                                                ? 'bg-red-600 text-white'
                                                : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                                                }`}
                                        >
                                            🇹🇷 BIST100
                                        </button>
                                        <button
                                            type="button"
                                            onClick={() => setNewMarket('binance')}
                                            className={`flex-1 px-4 py-2 rounded font-bold text-sm transition-colors ${newMarket === 'binance'
                                                ? 'bg-yellow-600 text-white'
                                                : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                                                }`}
                                        >
                                            ₿ Binance
                                        </button>
                                    </div>
                                </div>

                                <div>
                                    <label className="block text-gray-400 text-sm mb-1">Sembol</label>
                                    <input
                                        type="text"
                                        value={newTicker}
                                        onChange={(e) => setNewTicker(e.target.value)}
                                        placeholder={newMarket === 'bist100' ? 'THYAO' : 'BTC'}
                                        className="w-full bg-gray-800 border border-gray-700 text-white px-4 py-2 rounded font-mono uppercase"
                                        autoFocus
                                    />
                                </div>

                                {/* Toplu ekleme butonları */}
                                {newMarket === 'bist100' ? (
                                    <div className="space-y-2">
                                        <button
                                            type="button"
                                            onClick={addAllBist100}
                                            disabled={addingAllBist || addingBist30}
                                            className="w-full px-4 py-3 bg-gradient-to-r from-red-600 to-red-700 hover:from-red-700 hover:to-red-800 disabled:from-gray-600 disabled:to-gray-700 text-white rounded font-bold text-sm transition-all flex items-center justify-center gap-2"
                                        >
                                            {addingAllBist ? (
                                                <>
                                                    <span className="animate-spin">⏳</span>
                                                    BIST100 ekleniyor...
                                                </>
                                            ) : (
                                                <>
                                                    🇹🇷 Tüm BIST100'ü Ekle ({BIST100_TICKERS.length} hisse)
                                                </>
                                            )}
                                        </button>
                                        <button
                                            type="button"
                                            onClick={addAllBist30}
                                            disabled={addingAllBist || addingBist30}
                                            className="w-full px-4 py-2 bg-gradient-to-r from-red-500 to-red-600 hover:from-red-600 hover:to-red-700 disabled:from-gray-600 disabled:to-gray-700 text-white rounded font-bold text-sm transition-all flex items-center justify-center gap-2"
                                        >
                                            {addingBist30 ? (
                                                <>
                                                    <span className="animate-spin">⏳</span>
                                                    BIST30 ekleniyor...
                                                </>
                                            ) : (
                                                <>
                                                    🇹🇷 BIST30'u Ekle ({BIST30_TICKERS.length} hisse)
                                                </>
                                            )}
                                        </button>
                                    </div>
                                ) : (
                                    <button
                                        type="button"
                                        onClick={addTopCrypto}
                                        disabled={addingCrypto}
                                        className="w-full px-4 py-3 bg-gradient-to-r from-yellow-600 to-yellow-700 hover:from-yellow-700 hover:to-yellow-800 disabled:from-gray-600 disabled:to-gray-700 text-white rounded font-bold text-sm transition-all flex items-center justify-center gap-2"
                                    >
                                        {addingCrypto ? (
                                            <>
                                                <span className="animate-spin">⏳</span>
                                                Crypto ekleniyor...
                                            </>
                                        ) : (
                                            <>
                                                ₿ Top 10 Crypto Ekle ({TOP_CRYPTO_TICKERS.length} coin)
                                            </>
                                        )}
                                    </button>
                                )}

                                {addTickerError && (
                                    <div className="text-red-400 text-sm">{addTickerError}</div>
                                )}
                            </div>

                            <div className="flex gap-3 mt-6">
                                <button
                                    type="button"
                                    onClick={() => setShowAddTickerModal(null)}
                                    className="flex-1 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded font-bold text-sm transition-colors"
                                >
                                    İptal
                                </button>
                                <button
                                    type="submit"
                                    className="flex-1 px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded font-bold text-sm transition-colors"
                                >
                                    Ekle
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            {/* Chart Modal */}
            {chartModal && (
                <ChartModal
                    ticker={chartModal.ticker}
                    market={chartModal.market}
                    strategyId={chartModal.strategyId}
                    onClose={() => setChartModal(null)}
                />
            )}

            {/* Custom Confirm Modal */}
            {confirmModal && (
                <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
                    <div className="bg-gray-900 border border-gray-700 rounded-xl p-6 w-full max-w-md shadow-2xl">
                        <div className="flex items-center gap-3 mb-4">
                            <div className="w-12 h-12 rounded-full bg-red-500/20 flex items-center justify-center">
                                <span className="text-2xl">⚠️</span>
                            </div>
                            <h3 className="text-xl font-bold text-white">{confirmModal.title}</h3>
                        </div>

                        <p className="text-gray-300 mb-6 leading-relaxed">
                            {confirmModal.message}
                        </p>

                        <div className="flex gap-3">
                            <button
                                onClick={() => setConfirmModal(null)}
                                className="flex-1 px-4 py-3 bg-gray-700 hover:bg-gray-600 text-white rounded-lg font-bold transition-colors"
                            >
                                İptal
                            </button>
                            <button
                                onClick={confirmModal.onConfirm}
                                className="flex-1 px-4 py-3 bg-red-600 hover:bg-red-700 text-white rounded-lg font-bold transition-colors"
                            >
                                Sil
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
