import { useState, useEffect } from 'react';
import axios from 'axios';
import { Plus, Trash2, RefreshCw, TrendingUp, TrendingDown, Minus, Book, Zap } from 'lucide-react';
import DetailsModal from './DetailsModal';
import HelpModal from './HelpModal';
import RecommendationsModal from './RecommendationsModal';
import { useWebSocket } from '../contexts/WebSocketContext';
import { useToast } from '../contexts/ToastContext';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function Dashboard() {
    const [portfolio, setPortfolio] = useState([]);
    const [newTicker, setNewTicker] = useState('');
    const [loading, setLoading] = useState(false);
    const [selectedItem, setSelectedItem] = useState(null);
    const [showHelp, setShowHelp] = useState(false);
    const [showRecs, setShowRecs] = useState(false);

    const { lastMessage, isConnected } = useWebSocket();
    const { addToast } = useToast();

    useEffect(() => {
        fetchPortfolio(); // Initial load

        // Request Notification Permission (Safely)
        if ('Notification' in window && Notification.permission !== "granted") {
            try {
                Notification.requestPermission();
            } catch (e) {
                console.warn("Notification permission request failed:", e);
            }
        }
    }, []);

    // Handle WebSocket Updates
    useEffect(() => {
        if (lastMessage && lastMessage.type === 'PORTFOLIO_UPDATE') {
            const updatedItem = lastMessage.data;
            handleRealtimeUpdate(updatedItem);
        }
    }, [lastMessage]);

    const handleRealtimeUpdate = (updatedItem) => {
        setPortfolio(prev => {
            const exists = prev.find(p => p.ticker === updatedItem.ticker);

            // Notification Logic (Immediate)
            if (exists && exists.last_decision !== updatedItem.last_decision &&
                updatedItem.last_decision !== 'PENDING' && exists.last_decision !== 'PENDING') {
                sendNotification(updatedItem.ticker, updatedItem.last_decision);
            }

            if (exists) {
                return prev.map(p => p.ticker === updatedItem.ticker ? { ...p, ...updatedItem } : p);
            } else {
                // New item added via another client? Add it.
                return [...prev, updatedItem];
            }
        });

        // Update selected item detail view live
        if (selectedItem && selectedItem.ticker === updatedItem.ticker) {
            setSelectedItem(prev => ({ ...prev, ...updatedItem }));
        }
    };

    const fetchPortfolio = async () => {
        try {
            const res = await axios.get(`${API_URL}/portfolio`);
            const newData = res.data;

            // Update selected item if it's open (to show live updates in modal)
            if (selectedItem) {
                const updatedSelected = newData.find(p => p.ticker === selectedItem.ticker);
                if (updatedSelected) setSelectedItem(updatedSelected);
            }

            // Check for changes (Simple Notification Logic)
            if (portfolio.length > 0) {
                newData.forEach(newItem => {
                    const oldItem = portfolio.find(p => p.ticker === newItem.ticker);
                    if (oldItem && oldItem.last_decision !== newItem.last_decision && newItem.last_decision !== 'PENDING' && oldItem.last_decision !== 'PENDING') {
                        sendNotification(newItem.ticker, newItem.last_decision);
                    }
                });
            }

            setPortfolio(newData);
        } catch (err) {
            console.error("Error fetching portfolio:", err);
        }
    };

    const sendNotification = (ticker, decision) => {
        if ('Notification' in window && Notification.permission === "granted") {
            try {
                new Notification(`Signal Alert: ${ticker}`, {
                    body: `Model changed decision to: ${decision}`,
                    icon: '/vite.svg'
                });
            } catch (e) {
                console.warn("Notification creation failed:", e);
            }
        }
    };

    const addTicker = async (e) => {
        e.preventDefault();
        if (!newTicker) return;

        // Auto-append .IS logic for BIST
        let tickerToSend = newTicker.trim().toUpperCase();

        // If it doesn't have a dot suffix, assume it's BIST and append .IS
        // Except for common crypto pairs (checking generic length maybe? No, unsafe. Stick to user request "ben THYAO ekleyeyim ... .IS i kendi eklesin")
        if (!tickerToSend.includes('.')) {
            tickerToSend += '.IS';
        }

        try {
            setLoading(true);
            await axios.post(`${API_URL}/portfolio`, { ticker: tickerToSend });
            addToast(`${tickerToSend.replace('.IS', '')} portföye eklendi.`, "success");
            setNewTicker('');
            fetchPortfolio();
        } catch (err) {
            console.error("Error adding ticker:", err);
            addToast("Hisse eklenirken hata oluştu.", "error");
        } finally {
            setLoading(false);
        }
    };

    const removeTicker = async (e, ticker) => {
        e.stopPropagation(); // Prevent opening modal
        // Instant delete - No native confirmation

        try {
            // Optimistic UI update could be here, but for now just await
            await axios.delete(`${API_URL}/portfolio/${ticker}`);
            if (selectedItem?.ticker === ticker) setSelectedItem(null);
            addToast(`${ticker.replace('.IS', '')} listeden silindi.`, "success");
            fetchPortfolio();
        } catch (err) {
            console.error("Error removing ticker:", err);
            addToast("Silme işlemi başarısız oldu.", "error");
        }
    };

    const refreshAll = async () => {
        try {
            addToast("Arka plan analizi başlatıldı.", "info");
            await axios.post(`${API_URL}/refresh`);
        } catch (err) {
            console.error("Error refreshing:", err);
            addToast("Analiz başlatılamadı.", "error");
        }
    };

    return (
        <div className="min-h-screen bg-terminal-dark text-gray-200 p-8">
            <div className="max-w-6xl mx-auto">

                {/* Header */}
                <div className="flex justify-between items-center mb-8">
                    <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-green-400 to-blue-500">
                        RL Trading Asistanı
                    </h1>
                    <div className="flex gap-2">
                        {/* Connection Status Indicator */}
                        <div className="flex items-center gap-1 px-3 py-1 bg-gray-900 rounded border border-gray-700 text-xs font-mono">
                            <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`}></div>
                            {isConnected ? 'LIVE' : 'OFFLINE'}
                        </div>
                        <button onClick={() => setShowRecs(true)} className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 text-white rounded transition font-bold text-sm shadow-lg shadow-purple-900/20 animate-pulse">
                            <Zap size={18} fill="currentColor" className="text-yellow-300" /> AI TAVSİYE
                        </button>
                        <button onClick={() => setShowHelp(true)} className="flex items-center gap-2 px-4 py-2 bg-blue-600/20 text-blue-400 hover:bg-blue-600/30 rounded transition font-bold text-sm">
                            <Book size={18} /> REHBER
                        </button>
                        <button onClick={refreshAll} className="p-2 bg-gray-800 rounded hover:bg-gray-700 transition" title="Analizi Yenile">
                            <RefreshCw size={20} />
                        </button>
                    </div>
                </div>

                {/* Add Stock Form */}
                <form onSubmit={addTicker} className="flex gap-4 mb-12">
                    <input
                        type="text"
                        placeholder="Hisse Ekle (Örn: THYAO)"
                        value={newTicker}
                        onChange={(e) => setNewTicker(e.target.value)}
                        className="flex-1 p-4 rounded-lg bg-gray-800 border border-gray-700 focus:outline-none focus:border-green-500 text-lg uppercase"
                    />
                    <button type="submit" disabled={loading} className="px-8 py-4 bg-green-600 rounded-lg font-bold hover:bg-green-700 transition disabled:opacity-50">
                        {loading ? 'Ekleniyor...' : <Plus size={24} />}
                    </button>
                </form>

                {/* Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {portfolio.map((item) => (
                        <StockCard
                            key={item.ticker}
                            item={item}
                            onRemove={removeTicker}
                            onClick={() => setSelectedItem(item)}
                        />
                    ))}
                </div>

                {portfolio.length === 0 && (
                    <div className="text-center text-gray-500 mt-20">
                        Takip edilen hisse yok. Başlamak için yukarıdan ekleyin.
                    </div>
                )}

                {/* Details Modal */}
                {selectedItem && (
                    <DetailsModal item={selectedItem} onClose={() => setSelectedItem(null)} />
                )}

                {/* Help Modal */}
                {showHelp && (
                    <HelpModal onClose={() => setShowHelp(false)} />
                )}

                {/* Recommendations Modal */}
                {showRecs && (
                    <RecommendationsModal onClose={() => setShowRecs(false)} />
                )}
            </div>
        </div>
    );
}

function StockCard({ item, onRemove, onClick }) {
    const getStatusColor = (status) => {
        switch (status) {
            case 'BUY': return 'bg-green-900/30 border-green-500/50 text-green-400';
            case 'SELL': return 'bg-red-900/30 border-red-500/50 text-red-400';
            case 'HOLD': return 'bg-blue-900/30 border-blue-500/50 text-blue-400';
            default: return 'bg-gray-800 border-gray-700 text-gray-400';
        }
    };

    const getIcon = (status) => {
        switch (status) {
            case 'BUY': return <TrendingUp size={32} />;
            case 'SELL': return <TrendingDown size={32} />;
            case 'HOLD': return <Minus size={32} />;
            default: return <RefreshCw size={32} className="animate-spin" />;
        }
    };

    const formatVolume = (vol) => {
        if (!vol) return '0';
        if (vol >= 1000000) return (vol / 1000000).toFixed(1) + 'M';
        if (vol >= 1000) return (vol / 1000).toFixed(1) + 'K';
        return vol.toFixed(0);
    };

    return (
        <div
            onClick={onClick}
            className={`p-6 rounded-xl border-2 backdrop-blur-sm relative group transition-all duration-300 hover:scale-[1.02] cursor-pointer ${getStatusColor(item.last_decision)}`}
        >
            <button
                onClick={(e) => onRemove(e, item.ticker)}
                className="absolute top-4 right-4 p-1 text-gray-500 hover:text-red-400 opacity-0 group-hover:opacity-100 transition z-10"
            >
                <Trash2 size={18} />
            </button>

            <div className="flex justify-between items-start mb-4">
                <div>
                    <h2 className="text-2xl font-black tracking-wider">{item.ticker.replace('.IS', '')}</h2>
                    <div className="flex flex-col gap-0.5 mt-1">
                        <p className="text-sm opacity-70">{item.last_updated}</p>
                        {item.last_volume > 0 && (
                            <p className="text-xs font-mono opacity-60">
                                HACİM: {formatVolume(item.last_volume)}
                                {item.last_volume_ratio > 0 && (
                                    <span className={`ml-1 ${item.last_volume_ratio >= 1.5 ? 'text-green-400 font-bold' : item.last_volume_ratio <= 0.5 ? 'text-red-400' : 'text-gray-400'}`}>
                                        ({item.last_volume_ratio.toFixed(2)}x)
                                    </span>
                                )}
                            </p>
                        )}
                    </div>
                </div>
                <div className="p-2 rounded-full bg-white/5">
                    {getIcon(item.last_decision)}
                </div>
            </div>

            <div className="mt-6 flex items-end justify-between">
                <div>
                    <span className="text-xs uppercase tracking-widest opacity-60">FİYAT</span>
                    <div className="text-3xl font-mono font-medium">
                        {item.last_price > 0 ? item.last_price.toFixed(2) : '-.--'} <span className="text-lg">TL</span>
                    </div>
                </div>

                <div className="text-right">
                    <span className="text-xs uppercase tracking-widest opacity-60">KARAR</span>
                    <div className="text-xl font-bold">
                        {item.last_decision}
                    </div>
                </div>
            </div>
        </div>
    );
}
