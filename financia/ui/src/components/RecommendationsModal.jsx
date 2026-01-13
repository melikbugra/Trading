import { useState, useEffect } from 'react';
import axios from 'axios';
import { X, RefreshCw, TrendingUp, AlertTriangle, Zap } from 'lucide-react';
import { useWebSocket } from '../contexts/WebSocketContext';
import { useToast } from '../contexts/ToastContext';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default function RecommendationsModal({ onClose }) {
    const [recs, setRecs] = useState([]);
    const [loading, setLoading] = useState(false);

    // Scanning state is now global

    const { lastMessage, isScanning } = useWebSocket();
    const { addToast } = useToast();

    useEffect(() => {
        fetchRecs();
    }, []);

    useEffect(() => {
        if (lastMessage) {
            if (lastMessage.type === 'RECOMMENDATION_UPDATE') {
                const newItem = lastMessage.data;
                setRecs(prev => {
                    const filtered = prev.filter(r => r.ticker !== newItem.ticker);
                    const updated = [...filtered, newItem];
                    return updated.sort((a, b) => b.score - a.score);
                });

            } else if (lastMessage.type === 'SCAN_FINISHED') {
                // Global context update handles isScanning state.
                addToast("Piyasa taraması tamamlandı!", "success");
            }
        }
    }, [lastMessage]);

    const fetchRecs = async () => {
        try {
            const res = await axios.get(`${API_URL}/recommendations`);
            setRecs(res.data);
        } catch (err) {
            console.error("Error fetching recs:", err);
        }
    };

    const runScanner = async () => {
        try {
            // isScanning will update automatically via WS event
            // Clear old results immediately
            setRecs([]);
            await axios.post(`${API_URL}/recommendations/scan`);
        } catch (err) {
            console.error("Error starting scan:", err);
            addToast("Tarama başlatılamadı.", "error");
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/90 backdrop-blur-md">
            <div className="bg-gray-900 border border-gray-700 w-full max-w-4xl max-h-[90vh] rounded-2xl shadow-2xl flex flex-col overflow-hidden relative">

                {/* Header */}
                <div className="p-6 border-b border-gray-800 flex justify-between items-center bg-gray-900/50">
                    <div>
                        <h2 className="text-2xl font-black text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-purple-500 flex items-center gap-3">
                            <Zap className="text-yellow-400" />
                            AI MARKET TARAYICI
                        </h2>
                        <p className="text-sm text-gray-400 mt-1">BIST100 Yapay Zeka Destekli Fırsat Analizi</p>
                    </div>
                    <button onClick={onClose} className="p-2 hover:bg-red-500/10 hover:text-red-400 rounded-full transition">
                        <X size={24} />
                    </button>
                </div>

                {/* Toolbar */}
                <div className="p-4 bg-gray-800/30 flex justify-between items-center border-b border-gray-800">
                    <div className="text-xs text-gray-500">
                        {recs.length} Fırsat Bulundu
                    </div>
                    <button
                        onClick={runScanner}
                        disabled={isScanning}
                        className={`flex items-center gap-2 px-6 py-2 rounded-lg font-bold transition ${isScanning ? 'bg-gray-700 text-gray-400 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-700 text-white'}`}
                    >
                        <RefreshCw size={18} className={isScanning ? "animate-spin" : ""} />
                        {isScanning ? "TARANIYOR..." : "PIYASAYI TARA"}
                    </button>
                </div>

                {/* Content */}
                <div className="flex-1 overflow-y-auto p-0">
                    {recs.length === 0 ? (
                        <div className="flex flex-col items-center justify-center h-64 text-gray-500">
                            <RefreshCw size={48} className="mb-4 opacity-20" />
                            <p>Henüz bir fırsat bulunamadı veya tarama yapılmadı.</p>
                            <p className="text-sm mt-2">"Piyasayı Tara" butonuna basarak analizi başlatın.</p>
                        </div>
                    ) : (
                        <table className="w-full text-left">
                            <thead className="bg-gray-800/80 sticky top-0 backdrop-blur-sm z-10 text-xs uppercase tracking-wider text-gray-400 font-medium">
                                <tr>
                                    <th className="p-4">Hisse</th>
                                    <th className="p-4">Karar</th>
                                    <th className="p-4">AI Skor</th>
                                    <th className="p-4">Uyumsuzluk</th>
                                    <th className="p-4 text-right">Fiyat</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-800">
                                {recs.map((rec) => (
                                    <tr key={rec.ticker} className="hover:bg-white/5 transition group">
                                        <td className="p-4 font-black text-lg text-white">
                                            {rec.ticker.replace('.IS', '')}
                                            <div className="text-xs font-normal text-gray-500 opacity-60 group-hover:opacity-100">{rec.last_updated}</div>
                                        </td>
                                        <td className="p-4">
                                            <span className={`px-3 py-1 rounded text-xs font-bold ${rec.decision === 'STRONG BUY' ? 'bg-green-900 text-green-400 border border-green-500/50' : 'bg-blue-900 text-blue-400 border border-blue-500/50'}`}>
                                                {rec.decision}
                                            </span>
                                        </td>
                                        <td className="p-4 text-lg font-mono">
                                            <div className="flex items-center gap-2">
                                                <div className="w-24 h-2 bg-gray-700 rounded-full overflow-hidden">
                                                    <div className={`h-full ${rec.score >= 80 ? 'bg-green-500' : 'bg-blue-500'}`} style={{ width: `${rec.score}%` }}></div>
                                                </div>
                                                <span className={rec.score >= 80 ? 'text-green-400 font-bold' : 'text-blue-400'}>{rec.score.toFixed(0)}</span>
                                            </div>
                                        </td>
                                        <td className="p-4">
                                            {rec.divergence_count > 0 ? (
                                                <span className="flex items-center gap-1 text-yellow-400 font-bold bg-yellow-400/10 px-2 py-1 rounded w-fit text-sm">
                                                    <AlertTriangle size={14} />
                                                    {rec.divergence_count} Adet
                                                </span>
                                            ) : (
                                                <span className="text-gray-600 text-sm">-</span>
                                            )}
                                        </td>
                                        <td className="p-4 text-right font-mono text-lg text-gray-300">
                                            {rec.price.toFixed(2)} TL
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    )}
                </div>

                <div className="p-4 bg-gray-900 border-t border-gray-800 text-center text-xs text-gray-500">
                    * Öneriler 15dk gecikmeli veriye dayanır. Yatırım tavsiyesi değildir. Son kararı daima grafiğe bakarak veriniz.
                </div>
            </div>
        </div>
    );
}
